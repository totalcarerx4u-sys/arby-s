class Market:

    def __init__(self, event, exchange, yes_price, no_price):
        self.event = event
        self.exchange = exchange
        self.yes = yes_price
        self.no = no_price

    def __repr__(self):
        return f"{self.exchange} | {self.event} | YES:{self.yes} NO:{self.no}"