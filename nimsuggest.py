import subprocess
import sublime
import time
import sys
from queue import Queue
from threading import Thread
import os

isWindows = sys.platform == "win32"
settings = sublime.load_settings('NimPlus.sublime-settings')

if not isWindows:
	import select

nimsuggest_options = [
	"--stdin",
	"--debug",
	"--v2",
	"--maxresults:100"
]

if settings.get("nimplus.nimsuggest.options"):
	nimsuggest_options = settings.get("nimplus.nimsuggest.options")

def output_to_queue(output_stream, queue):
	if not isWindows:
		poll_obj = select.poll()
		poll_obj.register(output_stream, select.EPOLLIN)
		# Wait a bit for the object to be available for polling.
		while not output_stream.closed:
			if poll_obj.poll(1):
				if output_stream.closed: break
				line = output_stream.readline()
				if line == b'': break # means eof.
				queue.put(line)
		output_stream.close()
	else:
		for line in iter(output_stream.readline, b''):
			queue.put(line)
		output_stream.close()

def parent_directory(d):
	return os.path.abspath(os.path.join(d, os.pardir))

class SymbolDefinition:
	kind = ""
	shortName = ""
	fullname = ""
	symbolType = ""
	filename = ""
	line = 0
	col = 0
	docstring = ""
	raw = []

class Nimsuggest:
	"""
	Represents a nimsuggest instance.
	Reference: https://nim-lang.org/docs/nimsuggest.html
	"""
	def __init__(self, filePath):
		self.setup(filePath)

	def setup(self, filePath): 
		self.projectPath = parent_directory(filePath)
		self.filePath = filePath
		
		args = ["nimsuggest"] + nimsuggest_options
		if not isWindows:
			args.append("\""+ filePath +"\"")
		else:
			args.append(filePath)


		# Use shell=True to not have a terminal window poping up.
		if not isWindows:
			args = [" ".join(args)]

		self.process = subprocess.Popen(
			args,
			cwd=self.projectPath,
			stdin=subprocess.PIPE,
			stdout=subprocess.PIPE,
			stderr=subprocess.PIPE,
			shell=True
		)

		self.ready = False
		self.gettingReady = True
		self.input_queue = Queue()
		self.output_queue = Queue()
		self.stdout_thread = Thread(
			target=output_to_queue,
			args=(self.process.stdout, self.output_queue)
		)
		self.stderr_thread = Thread(
			target=output_to_queue,
			args=(self.process.stdout, self.output_queue)
		)
		self.stdout_thread.daemon = True
		self.stderr_thread.daemon = True

		self.stdout_thread.start()
		self.stderr_thread.start()

		# When nimsuggest starts, it spits out a bit of garbage.
		# We flush this garbage inside another thread to prevent
		# lag inside the editor
		t = Thread(target=self.flush_queue)
		t.daemon = True
		t.start()

	def flush_queue(self, waitTime = 2.0):
		time.sleep(waitTime)
		while not self.output_queue.empty():
			self.output_queue.get(block=False)
		self.ready = True
		self.gettingReady = False

	def tryRestart(self):
		"""
		If the underlying process is stopped, restart it.
		If it's already on, do nothing.
		"""
		if not self.ready and not self.gettingReady:
			self.setup(self.filePath)

	def write(self, message):
		try:
			self.process.stdin.write(message.strip().encode("utf-8"))
			self.process.stdin.write("\r\n".encode("utf-8"))
			self.process.stdin.flush()
			return True
		except:
			return False # error probably because the process died.
	def read(self):
		return self.process.stdout.readline().decode("utf-8").strip()

	def terminate(self):
		self.process.stdin.close()
		self.process.terminate()
		self.process.wait(timeout=0.2)

	def waitForOutput(self):
		while self.output_queue.empty():
			time.sleep(.01)

	def requestDefinition(self, filename, line, col, callback):
		"""
		Request symbol definition. Callback will be called with
		an "Definition" struct
		"""
		def processResponse():
			self.waitForOutput()
			try:
				data = []
				while not self.output_queue.empty(): # flush read.
					tmp = self.output_queue.get(block=False,timeout=1)
					decoded = tmp.decode("utf-8")
					if len(decoded.strip()) == 0: continue
					data = decoded.split("\t")
					
					if len(data) == 9:
						break
				if len(data) == 9:
					sd = SymbolDefinition()
					sd.kind = data[1]
					sd.fullname= data[2]
					sd.symbolType = data[3]
					sd.filename = data[4]
					sd.line = int(data[5])
					sd.col = int(data[6])
					sd.docstring = data[7]
					sd.raw = data
					callback(sd)
			except Exception as err:
				print("NimPlus:","Unexpected error:", sys.exc_info()[0])
				print(err)
				callback(None)
		# line are 1-indexed for nim.
		query = "def \"" + filename + "\":" + str(line+1) + ":" + str(col)
		self.flush_queue(0.0)
		res = self.write(query)
		if not res: # process died
			self.ready = False
			callback(None)
			return
		Thread(target=processResponse).start()

	def requestSuggestion(self, filename, line, col, callback):
		"""
		Request suggestions from nimsuggest. Return proposed
		suggestions by calling callback with as an argument an
		array of suggestions.
		Note that no matter what, at some point, callback
		will be called. And only once!
		"""
		def processResponse():
			# Wait for response ...
			self.waitForOutput()
			try:
				suggestions = []
				while not self.output_queue.empty(): # flush read.
					tmp = self.output_queue.get(block=False,timeout=1)
					decoded = tmp.decode("utf-8")
					if len(decoded.strip()) == 0: continue
					data = decoded.split("\t")

					if len(data) == 10:
						suggestions.append(data)
					if len(suggestions) > 1000:
						break # no need for tones of suggestions.
				while not self.output_queue.empty():
					self.output_queue.get(block=False,timeout=1)
				
				callback(suggestions)
				return
			except Exception as err:
				print("NimPlus:","Unexpected error:", sys.exc_info()[0])
				print(err)
				callback([])

		# lines are 1-indexed for nimsuggest.
		query = "sug \"" + filename + "\":" + str(line+1) + ":" + str(col)
		self.flush_queue(0.0)
		res = self.write(query)
		if not res:
			self.ready = False
			callback([])
			return
		t = Thread(target=processResponse)
		t.daemon = True
		t.start()

	def listUsages(self, filename, line, col):
		pass
	def renameSymbol(self, filename, line, col, newName):
		pass

