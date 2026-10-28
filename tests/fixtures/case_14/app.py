import escpos.printer as ep
p = ep.Serial("device")
p.qr("job")
