# GSM signal checker

A signal strength checker for GSM modems by Alexander Böhm (2015)

## Requirements

* python >= 2.7
* pyGObject
* pyGTK (for GUI mode)

## Usage
	gsmchecker.py [options] /dev/modem

	Options:
	--version     show program's version number and exit
	-h, --help    show this help message and exit
	-t            show signal strength as text
	-g            show signal strength as an tray icon (requires GTK)
	-i INTERVAL   interval in seconds between checks (default 60 seconds)
	
	Text mode options:
	-o, --once  check signal one time
	-j, --json  output format is json

GSM signal checker detects if you using X and start as tray. If no X detected
the checker starts in text mode. JSON as output format is support. For further
help look into the source.

