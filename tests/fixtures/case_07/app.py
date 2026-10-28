from win32print import OpenPrinter, WritePrinter
h = OpenPrinter("p")
WritePrinter(h, b"job")
