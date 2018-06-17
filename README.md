Media Organizer
===============

This script orders my media collection the way I like it.
It tries to look for the original date times of files by:
* getting image exif information
* matching certain path patterns
* averaging date times of other files in the folder


## Patterns

Patterns to detect a datetime of a file are a mix of regular expressions with datetime placeholders.
The default ones are:

```
/WhatsApp Image %Y-%m-%d at %I.%M.%S %p
/WhatsApp Image %Y-%m-%d at %H.%M.%S
/IMG_%Y%m%d_%H%M%S
/IMG-%Y%m%d-
/%Y-%m-%d.*/
'-%d-%m-%Y( |\.)
```

You can specify additional ones by passing one or more `--inpattern` parameters through the command line.

If you have some folder of specific files that you know the datetime of, you can also use a `regex;datetime` pattern,
and it also works with placeholders. For example `/holidays %Y/;%Y-08-15` would mark files in the `holidays 2015` folder
with the date of August the 15th.


## TODO

* allow for parenthesis inside DatetimePattern