import cups
self.conn = cups.Connection()
self.conn.printFile("p", "f", "t", {})
