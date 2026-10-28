from reportlab.pdfgen import canvas
c = canvas.Canvas("f.pdf")
c.drawString(1, 2, "job")
c.save()
