import win32print
h = win32print.OpenPrinter("p")
win32print.WritePrinter(h, b"job")
