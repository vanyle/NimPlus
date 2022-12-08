"""

Nim documentation uses a weird RST like format.
This file converts the RST into something that can be nicely displayed by Sublime.

"""

def cpublish_string(s):
	# A custom RST parser for poor people.
	# I won't use docutils.
	s = s.replace("\n","<br/>")
	s = s.replace("\\'","'")
	s = s.replace("\\\"","\"")

	# Replace `a` => <code>a</code>
	r = [] # string builder thing
	inCode = False

	for i in range(len(s)):
		if s[i] != '`':
			r.append(s[i])
		else:
			if inCode:
				r.append("</code>")
			else:
				r.append("<code>")
			inCode = not inCode

	# TODO: handle this
	"""
	.. code-block:: nim
		# some code written in nim
		# some more
	End of the indented block !
	"""

	return ''.join(r)