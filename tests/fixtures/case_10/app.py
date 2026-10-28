from escpos.printer import Usb
p = Usb(1, 2)
p.text("job")
