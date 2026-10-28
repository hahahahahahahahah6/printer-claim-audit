import win32print
win32print.StartDocPrinter(h, 1, ("job", None, "RAW"))
win32print.EndDocPrinter(h)
