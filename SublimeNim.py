import sublime_plugin
import sublime
import subprocess

from threading import Thread
import sys
import time



try:
	from queue import Queue, Empty
except ImportError:
	from Queue import Queue, Empty  # python 2.x
ON_POSIX = 'posix' in sys.builtin_module_names

def enqueue_output(out, queue):
	for line in iter(out.readline, b''):
		queue.put(line)
		# print(queue.qsize(),line)
	out.close()


package_name = 'SublimeNim'

# Used for executable management
def start(args,outputManager = False):
	# print("Running: "," ".join(args))
	p = subprocess.Popen(
		args,
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		shell=True, bufsize=1
	)
	q = None
	q2 = None
	if outputManager:
		q = Queue()
		q2 = Queue()
		t = Thread(target=enqueue_output, args=(p.stdout, q))
		t2 = Thread(target=enqueue_output, args=(p.stderr, q))
		t.daemon = True
		t2.daemon = True
		t.start()
		t2.start()
	# todo: close t when p dies
	return p,q,q2

def read(process):
	return process.stdout.readline().decode("utf-8").strip()


def write(process, message):
	try:
		process.stdin.write(message.strip().encode("utf-8"))
		process.stdin.write("\r\n".encode("utf-8"))
		process.stdin.flush()
		return True
	except:
		return False # error probably because the process died.

def terminate(process):
	process.stdin.close()
	process.terminate()
	process.wait(timeout=0.2)
# sanitize html:
def escape(html):
	return html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')


suggest_process = None
suggest_out = None

def attempt_start_suggest(filepath):
	global suggest_process,suggest_out
	if suggest_process == None:
		# Don't run the suggest on start up, just once a file is saved.
		suggest_process,suggest_out, dump = start(["nimsuggest.exe","--stdin","--debug",filepath],True)
		time.sleep(1)
		while not suggest_out.empty(): # flush read.
			suggest_out.get(block=False)


def fetch_suggestions(filepath,line,col):
	global suggest_process,suggest_out
	attempt_start_suggest(filepath)

	line += 1 # line are 1-indexed for nim.
	query = "sug \"" + filepath + "\":" + str(line) + ":" + str(col)
	while not suggest_out.empty(): # flush
		suggest_out.get(block=False)

	res = write(suggest_process,query)
	if not res: # process died
		suggest_process = None
		return
	while suggest_out.empty():
		time.sleep(.01)
	try:
		suggestions = []
		while not suggest_out.empty(): # flush read.
			tmp = suggest_out.get(block=False,timeout=1)
			data = tmp.decode("utf-8").split("\t")
			# print(len(data),data)
			if len(data) == 10:
				suggestions.append(data)
			if len(suggestions) > 1000:
				break # no need for tones of suggestions.

		while not suggest_out.empty(): suggest_out.get(block=False,timeout=1)
		return suggestions
		
	except Exception as err:
		print("Unexpected error:", sys.exc_info()[0])
		return []

# Hook to Package Manager events !

def plugin_loaded():
	from package_control import events

	if events.install(package_name):
		print('Installed %s!' % events.install(package_name))
	elif events.post_upgrade(package_name):
		print('Upgraded to %s!' % events.post_upgrade(package_name))

def plugin_unloaded():
	from package_control import events
	global suggest_process

	# Clean up:
	if suggest_process != None:
		try:
			terminate(suggest_process)
		except:
			pass
		suggest_process = None
	if events.pre_upgrade(package_name):
		print('Upgrading from %s!' % events.pre_upgrade(package_name))
	elif events.remove(package_name):
		print('Removing %s!' % events.remove(package_name))


if int(sublime.version()) < 3000:
	plugin_loaded()
	unload_handler = plugin_unloaded


maxErrorRegionCount = 0
class SublimeNimEvents(sublime_plugin.EventListener):
	def on_post_save_async(self,view):
		global maxErrorRegionCount
		filepath = view.file_name()
		if type(filepath) != str or not view.match_selector(0, "source.nim"):
			return
		# run check process
		check_process = start(["nim.exe","check","--stdout:on","--verbosity:0",filepath])[0]
		stdout,stderr = check_process.communicate(timeout=3)
		for i in range(maxErrorRegionCount+1):
			view.erase_regions("e" + str(i))

		lines = stdout.decode("utf-8").split("\n")
		maxErrorRegionCount = 0
		for check_message in lines:
			if len(check_message) > 3 and check_message.startswith(filepath):
				check_message = check_message[len(filepath):]
				# (line, col) Verbosity: Decription [Code]
				end = check_message.find(")")
				position = check_message[check_message.find("(")+1:end]
				line,col = position.split(",")
				line = int(line)
				col = int(col)

				description = check_message[end+1:]
				description = escape(description)
				msg_type = description.split(":")[0]

				pointStart = view.text_point(line-1,col-1)

				regionId = "e" + str(maxErrorRegionCount)
				maxErrorRegionCount += 1

				def on_close():
					view.erase_regions(regionId)
				def on_navigate():
					pass

				# print(msg_type)
				rcolor = "#f00" if msg_type.strip() == "Error" else "#00f"
				regcolor = "region.redish" if msg_type.strip() == "Error" else "region.cyanish"

				view.add_regions(
					regionId,
					[sublime.Region(pointStart, pointStart)],
					"region.redish",
					"comment",
					sublime.DRAW_EMPTY,
					[description], # HTML format
					rcolor,
					on_navigate,
					on_close) # left border
			terminate(check_process)
	def on_hover(self, view, point, hover_zone):
		# Show documentation and handle the "GOTO definition"
		filepath = view.file_name()
		if type(filepath) != str or not view.match_selector(point, "source.nim"):
			return
		global suggest_process,suggest_out
		attempt_start_suggest(filepath)
			
		line,col = view.rowcol(point)
		line += 1 # line are 1-indexed for nim.
		query = "def \"" + filepath + "\":" + str(line) + ":" + str(col)

		while not suggest_out.empty(): # flush
			suggest_out.get(block=False)

		res = write(suggest_process,query)
		if not res: # process died
			suggest_process = None
			return
		while suggest_out.empty():
			time.sleep(.01)
		try:
			data = []
			while not suggest_out.empty(): # flush read.
				tmp = suggest_out.get(block=False,timeout=1)
				data = tmp.decode("utf-8").split("\t")
				if len(data) == 9:
					break

			# data[1] = skVar
			# data[2] = filename.symbolname
			# data[3] = type
			# data[4] = file of definition
			# data[5] = line of definition
			# data[6] = col of definition
			# data[7] = Doc string
			if len(data) == 9:
				docstr = data[7].replace("\\x0A","\n")[1:-1]
				body = """
					<style>
						h4{ margin:0;padding:0; }
					</style>
					<h4>%s</h4>
					<div>
					<a href="%s,%s,%s">%s(%s,%s)</a>
					</div>
					<div>
						%s
					</div>
				""" % (escape(data[3]),
						data[4],data[5],data[6],
						data[4],data[5],data[6],
					escape(docstr)) # docstr are markdown formatted.

				def on_navigate(href):
					file,line,col = href.split(",")
					affected_view = view
					if file != filepath:
						affected_view = view.window().open_file(file)
					def navigator(aview,line,col):
						counter = 0
						while aview.is_loading() and counter < 100:
							time.sleep(0.03) # 30 ms
							counter += 1
						line = int(line)-1
						col = int(col)
						aview.show(aview.text_point(line,col),True,False,False)

					# Do this on another thread:
					t = Thread(target=navigator, args=(affected_view, line,col))
					t.daemon = True # thread dies with the program
					t.start()
				def on_hide():
					pass

				view.show_popup(
					body,
					sublime.HIDE_ON_MOUSE_MOVE_AWAY,
					point,
					600,
					100,
					on_navigate,
					on_hide
				)
		except Exception as err:
			print("Unexpected error:", sys.exc_info()[0])
			pass
	def on_query_completions(self, view, prefix, locations):
		filepath = view.file_name()
		if type(filepath) != str or not view.match_selector(locations[0], "source.nim"):
			return
		global suggest_process,suggest_out
		
		line,col = view.rowcol(locations[0])
		lst = sublime.CompletionList()

		# Fetch the suggestions async.
		def fillCompletions(lst,prefix):
			suggestions = fetch_suggestions(filepath,line,col)
			# print([i[2] for i in suggestions])
			completions = []
			for i in suggestions:
				docstr = i[7].replace("\\x0A","\n")[1:-1]
				item = sublime.CompletionItem(
					i[2], # trigger is empty.
					i[3], # annotation (displayed on the right)
					i[2], # completion (will be inserted)
					details="<div>%s</div>" % escape(docstr)
				)
				completions.append(item)
			lst.set_completions(completions)

		t = Thread(target=fillCompletions, args=(lst,prefix,))
		t.daemon = True
		t.start()

		return lst

class CompileNimCommand(sublime_plugin.WindowCommand):
	def run(self):
		view = self.window.active_view()

		point = view.sel()[0].begin()
		filepath = view.file_name()
		if type(filepath) != str or not view.match_selector(point, "source.nim"):
			return
		
		# "--stdout:on"
		com = ["nim","c","--colors",filepath]
		print(" ".join(com))

		proc,stdout,stderr = start(com,True)
		self.window.destroy_output_panel("compilation")
		new_view = self.window.create_output_panel("compilation",False)
		self.window.run_command("show_panel", {"panel": "output.compilation"})
		
		def async_fill():
			while proc.poll() is None:
				time.sleep(0.01)
				while not stdout.empty():
					l = stdout.get(block=False)
					print(l)
					l = l.decode("utf-8")
					# new_view.run_command("append", {"characters": "[31m"})
					new_view.run_command("append", {"characters": l})
			# Apply the ANSI theme at the end because it's readonly.
			new_view.run_command("ansi", args={"clear_before": True})
		t = Thread(target=async_fill)
		t.daemon = True
		t.start()

class RunNimCommand(sublime_plugin.WindowCommand):
	def run(self):
		view = self.window.active_view()
		point = view.sel()[0].begin()
		filepath = view.file_name()
		if type(filepath) != str or not view.match_selector(point, "source.nim"):
			return
		
		# "--stdout:on"
		com = ["nim","r","--colors",filepath]
		print(" ".join(com))

		proc,stdout,stderr = start(com,True)
		self.window.destroy_output_panel("compilation")
		new_view = self.window.create_output_panel("compilation",False)
		self.window.run_command("show_panel", {"panel": "output.compilation"})
		
		def async_fill():
			while proc.poll() is None:
				time.sleep(0.01)
				while not stdout.empty():
					l = stdout.get(block=False)
					print(l)
					l = l.decode("utf-8")
					# new_view.run_command("append", {"characters": "[31m"})
					new_view.run_command("append", {"characters": l})
			# Apply the ANSI theme at the end because it's readonly.
			new_view.run_command("ansi", args={"clear_before": True})
		t = Thread(target=async_fill)
		t.daemon = True
		t.start()

class SublimeNimOpenSiteCommand(sublime_plugin.WindowCommand):
	def run(self, args):
		print(args)