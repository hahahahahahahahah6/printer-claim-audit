import win32print
win32print.WritePrinter(win32print.OpenPrinter("p"), b"job")
