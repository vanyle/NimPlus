SublimeNim
=======

Nim Programming Language plugin for Sublime Text 4

Requires version 4073 or higher.

Features
--------

* Syntax highlighting
* Highlight errors (Using `nim check`)
* Show tooltips with type informations
* Goto Definition (link inside tooltip)
* Autocompletion (based on `nimsuggest`)
* Shows your documentation
* Keyshortcuts for building and generation documentation

![demo](example.png)

TODO (Ordered by priority)
-------
* Handle settings
* Polish features
* Write doc

Installation
------------

*Package Control* is required. Find how to install it here: https://packagecontrol.io/installation
If you have other packages installed, you probably also have already installed *Package Control*.

1. <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> 
2. Select `Package Control: Add repository`
3. Enter URL: https://github.com/vanyle/SublimeNim
4. `Install package` 
5. `SublimeNim` 
6. `Enter`

Settings, Usage and Tips
------------------------

Depending on how much you want Sublime to behave as an IDE or as a text editor, you can toggle the following features:

## Error highlighting


Add `"show_definitions": false` in your settings file to disable the default sublime text definitions and
use the SublimeNim definitions instead.

See Preferences -> PackageSettings -> SublimeNim

## Tooltips



## Auto completion

This means <kbd>Ctrl</kbd>+<kbd>Space</kbd> has to be pressed again to fetch Nim compiler completions.
It can also be set into an immediate mode.


Contributing
------------

Pull requests are **not** welcome. Fork this project if you want to add stuff.
Open an issue if you have a problem.in