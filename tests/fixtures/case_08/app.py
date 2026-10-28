import win32print
self.h = win32print.OpenPrinter("p")
win32print.WritePrinter(self.h, b"job")
