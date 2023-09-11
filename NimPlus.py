import sublime_plugin
import sublime
import subprocess
import sys, os, time, traceback

import webbrowser
from threading import Thread
from queue import Queue

from NimPlus.nimsuggest import Nimsuggest, SymbolDefinition
from NimPlus.docdisplay import cpublish_string

isWindows = sys.platform == "win32"
settings = sublime.load_settings('NimPlus.sublime-settings')
suggestionEngine = None # Can be a nimsuggest instance if needed.

def enqueue_output(out, queue):
	for line in iter(out.readline, b''):
		queue.put(line)
		# print("NimPlus:",queue.qsize(),line)
	out.close()

# Used for executable management
def start(args, outputManager = False, cwd = None):
	# print("NimPlus:","Running: "," ".join(args))
	if not isWindows:
		args = [" ".join(args)]

	process = subprocess.Popen(
		args,
		cwd=cwd,
		stdin=subprocess.PIPE,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		shell=True, bufsize=1
	)
	stdout_queue = None
	stderr_queue = None

	if outputManager:
		stdout_queue = Queue()
		stderr_queue = Queue()
		t = Thread(target=enqueue_output, args=(process.stdout, stdout_queue))
		t2 = Thread(target=enqueue_output, args=(process.stderr, stderr_queue))
		t.daemon = True
		t2.daemon = True
		t.start()
		t2.start()

	return process, stdout_queue, stderr_queue

def terminate(process):
	process.stdin.close()
	process.terminate()
	process.wait(timeout=0.2)
# sanitize html:
def escape(html):
	return html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#39;')


# Hook to Package Manager events !

def plugin_loaded():
	global settings
	settings = sublime.load_settings('NimPlus.sublime-settings')

def plugin_unloaded():
	global suggestionEngine

	# Clean up
	if suggestionEngine != None:
		try:
			suggestionEngine.terminate()
		except:
			pass
		suggestionEngine = None

maxErrorRegionCount = 0
error_body_table = {}

class NimPlusEvents(sublime_plugin.EventListener):
	def on_post_save_async(self,view: sublime.View):
		global settings
		if not settings.get("nimplus.savecheck"):
			return

		filepath = view.file_name()
		if type(filepath) != str or not view.match_selector(0, "source.nim"):
			return
		if filepath.endswith(".nimble"):
			# No check. We could inject nimble_injection into it to have
			# proper error checking but .nimble files usually contain very simple
			# code that is not very error prone, so I don't feel like this feature
			# is worth it.
			return

		# run check process
		view.window().status_message("Checking program validity ...")

		nim_args = settings.get("nimplus.nim.arguments")

		def check_program(filepath):
			global maxErrorRegionCount

			nim_checking_command = ["nim","check"] + nim_args
			if not isWindows:
				nim_checking_command.append("\""+ filepath +"\"")
			else:
				nim_checking_command.append(filepath)

			checking_process, _, _ = start(nim_checking_command)
			stdout, _ = checking_process.communicate()

			for i in range(maxErrorRegionCount+1):
				regionId = "e" + str(i)
				if regionId in error_body_table:
					del error_body_table[regionId]
				view.erase_regions(regionId)

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
					# To compute point end,
					# we need to find the token length as errors seem to
					# always span exactly one token in Nim.
					wordRegion = view.word(pointStart)

					regionId = "e" + str(maxErrorRegionCount)
					maxErrorRegionCount += 1

					def on_close():
						view.erase_regions(regionId)
					def on_navigate():
						pass

					rcolor = "#f00" if msg_type.strip() == "Error" else "#00f"
					regcolor = "region.redish" if msg_type.strip() == "Error" else "region.cyanish"

					region_draw_flag = sublime.DRAW_SQUIGGLY_UNDERLINE + sublime.DRAW_NO_FILL + sublime.DRAW_NO_OUTLINE
					error_body_table[regionId] = description

					view.add_regions(
						key=regionId,
						regions=[wordRegion],
						scope=regcolor,
						icon="panel_close", # a 'x' icon
						flags=region_draw_flag,
					#	annotations=[description], # HTML format
						annotation_color=rcolor,
						on_navigate=on_navigate,
						on_close=on_close) # left border
				try:
					terminate(checking_process)
				except: # ProcessLookupError mostly.
					pass
			view.window().status_message("Check completed.")

		t = Thread(target=check_program, args=(filepath,))
		t.daemon = True
		t.start()

	def on_hover(self, view: sublime.View, point, hover_zone):
		# Show documentation and handle the "GOTO definition"
		global settings, suggestionEngine
		if not settings.get("nimplus.hoverdescription"):
			return
		filepath = view.file_name()
		if type(filepath) != str or not view.match_selector(point, "source.nim"):
			return

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

		popup_flags = sublime.HIDE_ON_MOUSE_MOVE_AWAY

		for i in range(maxErrorRegionCount+1):
			regionId = "e" + str(i)
			regions = view.get_regions(regionId)
			if len(regions) == 0: break
			r = regions[0]
			if r.contains(point):
				errText = "Error"
				if regionId in error_body_table:
					errText = error_body_table[regionId]
				view.show_popup(
					content=errText,
					flags=popup_flags,
					location=point,
					max_width=600,
					max_height=150,
					on_navigate=on_navigate,
					on_hide=on_hide
				)
				return

		if suggestionEngine == None:
			suggestionEngine = Nimsuggest(filepath)
		suggestionEngine.tryRestart()

		# Check if the mouse is over an error.
		# In that case, show the error.

		def on_result(suggestion: SymbolDefinition):
			if suggestion == None:
				return
			docstr = suggestion.docstring.replace("\\x0A","\n")[1:-1]
			docstr = escape(docstr)
			docstr = cpublish_string(docstr)
			# Convert RST to HTML.
			
			body = """
				<body id="NimPlus">
				<style>
					h4{
						background-color: color(var(--background) alpha(0.25));
						margin: 0;
						padding: 5px;
					}
					#NimPlus code{
						font-family: "Consolas", monospace;
					}
					#NimPlus{
						margin: 0;
						padding: 0;
					}
					#NimPlus #desc_block{
						padding: 5px;
						font-family: "Roboto", "Lato", Arial, sans-serif;
					}
				</style>
				<h4>%s</h4>
				<div id="desc_block">
				<a href="%s,%s,%s">
					%s(%s,%s)
				</a>
				<div>
					%s
				</div>
				</div>
				</body>
			""" % (
				escape(suggestion.symbolType),
				suggestion.filename,suggestion.line,suggestion.col,
				suggestion.filename,suggestion.line,suggestion.col,
				docstr
			)

			view.show_popup(
				content=body,
				flags=popup_flags,
				location=point,
				max_width=600,
				max_height=150,
				on_navigate=on_navigate,
				on_hide=on_hide
			)
		
		line,col = view.rowcol(point)
		suggestionEngine.requestDefinition(filepath, line, col, on_result)


	def on_query_completions(self, view, prefix, locations):
		global settings, suggestionEngine
		
		if not settings.get("nimplus.autocomplete"):
			return
		# don't offer anything for multiple cursors
		if len(locations) > 1:
			return ([], 0)
		filepath = view.file_name()
		if type(filepath) != str or not view.match_selector(locations[0], "source.nim"):
			return

		if suggestionEngine == None:
			suggestionEngine = Nimsuggest(filepath)
		suggestionEngine.tryRestart()
		view.run_command("save")

		line,col = view.rowcol(locations[0])
		# Needed for async completion instead of regular []
		lst = sublime.CompletionList(flags = sublime.INHIBIT_WORD_COMPLETIONS)

		# Fetch the suggestions async.
		def fillCompletions(suggestions):
			global ready
			# We need to save the file for nimsuggest to work properly here.
			# view.run_command("save")
			completions = []
			
			for i in suggestions:
				# i[1] = skMacro, skProc, skType, skIterator, skTemplate, skFunc
				#        skEnumField, skConst, skVar, skLet
				kind = sublime.KIND_AMBIGUOUS
				if i[1] in ["skMacro","skProc","skIterator","skTemplate","skFunc"]:
					kind = sublime.KIND_FUNCTION
				elif i[1] in ["skConst","skLet","skVar","skEnumField","skField"]:
					kind = sublime.KIND_VARIABLE
				elif i[1] in ["skType"]:
					kind = sublime.KIND_TYPE
				toComplete = i[2].split(".")
				toComplete = toComplete[-1] # Remove the package prefix.

				docstr = i[7].replace("\\x0A","\n")[1:-1]
				# source = """http:open_recent_file""" #  {"file": "%s"} % i[4] # + "," + i[5] + "," + i[6]
				# sourcelink = "<a href='%s'>Source</a> " % source
				if len(docstr) >= 90:
					docstr = docstr[:90] # maxlen: 60 chars to avoid having a big completion window.

				details = "<div>%s</div>" % escape(docstr)

				item = sublime.CompletionItem(
					trigger = toComplete, # trigger is empty.
					annotation = i[3], # annotation (displayed on the right). We display the type.
					completion = toComplete, # completion (will be inserted)
					details = details, # displayed at the bottom, we display the documentation of the item
					kind = kind # icon on the left.
				)
				completions.append(item)
			
			lst.set_completions(completions, sublime.INHIBIT_WORD_COMPLETIONS)

		suggestionEngine.requestSuggestion(filepath, line, col, fillCompletions)
		
		return lst

proc = None

def run_in_terminus(window,commands,cwd):
	str_com = ""
	for argument in commands:
		if " " not in argument:
			str_com += argument + " "
		else:
			str_com += '"' + argument.replace('"','\\"') + '" '

	window.run_command("terminus_open",{
        "cwd": cwd,
        "shell_cmd": str_com,
        "title":"Nim",
        "auto_close": False
	})

	return


def execute_nim_command_on_file(commands,comobj):
	global proc
	view = comobj.window.active_view()

	if settings.get("nimplus.nim.save_before_build"):
		view.run_command("save")

	point = view.sel()[0].begin()
	filepath = view.file_name()
	if type(filepath) != str or not view.match_selector(point, "source.nim"):
		return
	if proc != None and proc.poll() is None: # kill the running process.
		proc.terminate()

	com = commands

	# "--stdout:on"
	if settings.get("nimplus.use_terminus"):
		com.append(filepath)
		cwd = os.path.dirname(os.path.abspath(filepath))
		run_in_terminus(comobj.window,com,cwd)
		return

	# This is not needed for terminus to work.
	if not isWindows:
		com.append("\""+ filepath +"\"")
	else:
		com.append(filepath)

	proc, stdout = start(com,True)
	comobj.window.destroy_output_panel("compilation")
	new_view = comobj.window.create_output_panel("compilation",False)
	comobj.window.run_command("show_panel", {"panel": "output.compilation"})

	def async_fill():
		while proc.poll() is None:
			time.sleep(0.01)
			while not stdout.empty():
				l = stdout.get(block=False)
				l = l.decode("utf-8")
				new_view.run_command("append", {"characters": l})
		# Apply the ANSI theme at the end because it's readonly.
		new_view.run_command("ansi", args={"clear_before": True})
	t = Thread(target=async_fill)
	t.daemon = True
	t.start()
def execute_nim_command_on_project(commands,comobj,noFilename = False):
	# commands is an array like ["nim","doc"] for example.
	global proc
	view = comobj.window.active_view()

	if settings.get("nimplus.nim.save_before_build"):
		view.run_command("save")

	point = view.sel()[0].begin()
	filepath = view.file_name()
	if type(filepath) != str or not view.match_selector(point, "source.nim"):
		return
	if proc != None and proc.poll() is None: # kill the running process.
		proc.terminate()

	p = os.path.abspath(filepath)
	found = False
	for i in range(100):
		if p == os.path.dirname(p):
			break
		if not os.path.isdir(p):
			p = os.path.dirname(p)
			continue
		files = [x for x in os.listdir(p) if (x.endswith(".nimble") and os.path.isfile(os.path.join(p,x)))]
		if len(files) <= 0:
			p = os.path.dirname(p)
			continue
		else:
			found = True
			break

	# move up the filepath until we find a .nimble file. 
	if not found:
		comobj.window.destroy_output_panel("compilation")
		new_view = comobj.window.create_output_panel("compilation",False)
		comobj.window.run_command("show_panel", {"panel": "output.compilation"})
		new_view.run_command("append", {"characters": "The file is not part of a nimble project.\n"})
		new_view.run_command("append", {"characters": "Run 'nimble init' to create a nimble project here."})
		new_view.run_command("ansi", args={"clear_before": True})
		return

	# "--stdout:on"
	com = commands
	if not noFilename:
		com.append(filepath)

	if settings.get("nimplus.use_terminus"):
		run_in_terminus(comobj.window,com,p)
		return

	proc,stdout,stderr = start(com,True,cwd = str(p))
	comobj.window.destroy_output_panel("compilation")
	new_view = comobj.window.create_output_panel("compilation",False)
	comobj.window.run_command("show_panel", {"panel": "output.compilation"})
	
	def async_fill():
		while proc.poll() is None:
			time.sleep(0.01)
			while not stderr.empty():
				l = stderr.get(block=False)
				l = l.decode("utf-8")
				new_view.run_command("append",{"characters":l})
			while not stdout.empty():
				l = stdout.get(block=False)
				l = l.decode("utf-8")
				new_view.run_command("append", {"characters": l})
		# Apply the ANSI theme at the end because it's readonly.
		new_view.run_command("ansi", args={"clear_before": True})
	t = Thread(target=async_fill)
	t.daemon = True
	t.start()

class CompileNimCommand(sublime_plugin.WindowCommand):
	def run(self, **kwargs):
		com = ["nim","c"]
		nim_args = settings.get("nimplus.nim.arguments")
		more_args = []
		if "arguments" in kwargs:
			more_args = kwargs["arguments"]

		execute_nim_command_on_file(com + nim_args + more_args,self)

class RunNimCommand(sublime_plugin.WindowCommand):
	def run(self, **kwargs):
		args = settings.get("nimplus.nim.console")
		args.reverse()
		
		nim_args = settings.get("nimplus.nim.arguments")
		more_args = []
		if "arguments" in kwargs:
			more_args = kwargs["arguments"]

		com = ["nim","r"]
		com += nim_args
		com += more_args

		if type(args) == list:
			for i in args:
				com.insert(0,i)
		execute_nim_command_on_file(com,self)

class RunNimbleCommand(sublime_plugin.WindowCommand):
	def run(self, **kwargs):
		args = settings.get("nimplus.nimble.console")
		args.reverse()
		com = ["nimble","run"]

		more_args = []
		if "arguments" in kwargs:
			more_args = kwargs["arguments"]
		com += more_args

		if type(args) == list:
			for i in range(len(args)):
				com.insert(i,args[i])
		execute_nim_command_on_project(com,self,noFilename = True)

class CompileNimbleCommand(sublime_plugin.WindowCommand):
	def run(self, **kwargs):
		com = ["nimble","build"]
		more_args = []
		if "arguments" in kwargs:
			more_args = kwargs["arguments"]
		com += more_args

		execute_nim_command_on_project(com,self,noFilename = True)

class RefreshNimbleCommand(sublime_plugin.WindowCommand):
	def run(self):
		execute_nim_command_on_project(["nimble","refresh"],self,noFilename = True)

class CheckNimbleCommand(sublime_plugin.WindowCommand):
	def run(self):
		execute_nim_command_on_project(["nimble","check"],self, noFilename = True)

class DocumentNimCommand(sublime_plugin.WindowCommand):
	def run(self):
		execute_nim_command_on_project(["nim","doc","--project","--outdir:htmldocs","--index:on"],self)

class PrettifyNimCommand(sublime_plugin.WindowCommand):
	def run(self):
		view = self.window.active_view()
		filepath = view.file_name()
		p = subprocess.Popen(["nimpretty",filepath])


class OpenDocumentNimCommand(sublime_plugin.WindowCommand):
	def run(self):
		view = self.window.active_view()
		filepath = view.file_name()
		p = os.path.abspath(filepath)
		found = False
		for i in range(100):
			if os.path.dirname(p) == p:
				break
			if not os.path.isdir(p):
				p = os.path.dirname(p)
				continue
			files = [x for x in os.listdir(p) if (x.endswith(".nimble") and os.path.isfile(os.path.join(p,x)))]
			if len(files) <= 0:
				p = os.path.dirname(p)
				continue
			else:
				found = True
				break

		# move up the filepath until we find a .nimble file. 
		if not found:
			sublime.message_dialog("Documentation not found.")

		p = os.path.join(p,"htmldocs/theindex.html")
		webbrowser.open_new_tab("file:///" + p)


class NimPlusOpenSiteCommand(sublime_plugin.WindowCommand):
	def run(self, url):
		webbrowser.open_new_tab(url)
