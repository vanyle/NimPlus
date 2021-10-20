SublimeNim
=======

Nim Programming Language plugin for Sublime Text 2/3

Features
--------

* Syntax highlighting
* Highlight errors (Using `nim check`)
* Show tooltips with type informations
* Goto Definition (link inside tooltip)
* Autocompletion (based on `nimsuggest`)
* Keyshortcuts for building.

![demo](example.png)

TODO (Ordered by priority)
-------
* Handle settings
* Auto completion
* Build shortcut
* Code snippets

Installation
------------

Use package control:

1. <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> 
2. `Install package` 
3. `SublimeNim` 
4. `Enter`

Settings
--------

Add `"show_definitions": false` in your settings file to disable the default sublime text definitions and
use the SublimeNim definitions instead.

See Preferences -> PackageSettings -> NimLime

Autocompletion works per default in an on-demand mode.
This means <kbd>Ctrl</kbd>+<kbd>Space</kbd> has to be pressed again to fetch Nim compiler completions.
It can also be set into an immediate mode.

If auto-completions don't work copy the `nim_update_completions` block from the NimLime
default key bindings file to the user key bindings file.

Checking the current file automatically on-save can be enabled through the setting `check.on_save.enabled`.

The path to the compiler can be configured through the setting `nim.executable`.
Per default it is set to `nim`, which means that the compiler must be in your `PATH` for the plugin to work.

Usage and tips
--------------



Contributing
------------

Pull requests are not welcome. Fork this project if you want to add stuff.
