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

You should install the `ANSIescape` package to enjoy the syntax coloring of the terminal when building.
This is optional.

Depending on how much you want Sublime to behave as an IDE or as a text editor, you can toggle the following features.
You can see all the toggles inside your preference file.

Open it with: Preferences > Package Settings > SublimeNim > Settings - Default

### Error highlighting

Toggle with `sublimenim.savecheck`

After saving, will check the current file for errors. See screenshot above.

### Tooltips

Toggle with `sublimenim.hoverdescription`

Will show the types and the docstring of the variable and procedure you hover over.

### Auto completion

Toggle with `sublimenim.autocomplete`

Will propose completion options based on `nimsuggest`'s `sug` feature.

### Build shortcuts

<kbd>Ctrl</kbd>+<kbd>B</kbd> : Compile and Run the current file
<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>B</kbd> : Compile the current file  

You can change these with: Preferences > Package Settings > SublimeNim > Key Bindings - Default

TODO
-------
- [ ] nimble integration: Build/Run projects instead of files
- [ ] nimble doc integration: Command to generate documentation and open it
- [ ] Remove memory leaks when reloading the plugin because of program handles that are not closed

Contributing
------------

Pull requests are **not** welcome. Fork this project if you want to add stuff.
Open an issue if you have a problem.