def check_arbitrage(ibkr, kalshi):

    ib_dem = ibkr.get("DEMOCRAT")
    ib_rep = ibkr.get("REPUBLICAN")

    ka_dem = kalshi.get("DEMOCRAT")
    ka_rep = kalshi.get("REPUBLICAN")

    if ib_dem is None or ib_rep is None:
        return

    if ka_dem is None or ka_rep is None:
        return

    print("\n--- PRICE SNAPSHOT ---")
    print("IBKR DEM:", ib_dem)
    print("IBKR REP:", ib_rep)
    print("KALSHI DEM:", ka_dem)
    print("KALSHI REP:", ka_rep)

    # Arbitrage case 1
    total = ib_dem + ka_rep

    if total < 1:
        profit = 1 - total

        print("\nARBITRAGE FOUND")
        print("Buy Democrat on IBKR:", ib_dem)
        print("Buy Republican on Kalshi:", ka_rep)
        print("Profit:", round(profit * 100, 2), "%")

    # Arbitrage case 2
    total = ka_dem + ib_rep

    if total < 1:
        profit = 1 - total

        print("\nARBITRAGE FOUND")
        print("Buy Democrat on Kalshi:", ka_dem)
        print("Buy Republican on IBKR:", ib_rep)
        print("Profit:", round(profit * 100, 2), "%")