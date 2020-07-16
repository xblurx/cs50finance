from cs50 import SQL
from flask import render_template, redirect
from helpers import lookup, usd


class SqlHandler:

    def __init__(self, database):
        self.db = SQL(database)

    def get_current_stocks(self, username: list, user_id):
        """Query database to get user holdings"""

        cash_left = self.db.execute("SELECT cash FROM users WHERE username = ?", username)[0]["cash"]
        user_stocks = self.db.execute("""SELECT DISTINCT ticker
                                    FROM holdings
                                    JOIN users ON holdings.user_id = users.id
                                    WHERE username = ?""",
                                      username
                                      )

        holdings_inf = self.db.execute("""SELECT ticker, company_name, SUM(shares), price, SUM(total)
                                        FROM holdings
                                        WHERE user_id = ?
                                        GROUP BY ticker
                                        ORDER BY price DESC
                                        """,
                                       user_id
                                       )

        total_value = 0
        for x in range(len(holdings_inf)):
            holdings_inf[x]["price"] = round(lookup(holdings_inf[x]["ticker"])["price"], 2)
            holdings_inf[x]["SUM(total)"] = round(holdings_inf[x]["SUM(shares)"] * holdings_inf[x]["price"], 2)
            total_value += float(holdings_inf[x]["SUM(total)"])

        total_value += float(cash_left)

        return render_template("index.html", data=holdings_inf, cash=usd(cash_left), total=usd(round(total_value, 2)))

    def first_purchase(self, username: list, user_id, ticker, amount, date):
        """
        Initially query database when user buys the first time.
        Updates cash left, inserts holdings and history data.
        """
        amount_to_pay = float(amount) * lookup(ticker)["price"]
        self.db.execute(
            "INSERT INTO holdings (user_id, ticker, company_name, shares, price, total) VALUES (?, ?, ?, ?, ?, ?)",
            user_id,
            ticker.upper(),
            lookup(ticker)["name"],
            int(amount),
            float(lookup(ticker)["price"]),
            amount_to_pay
        )
        self.db.execute("UPDATE users SET cash = cash - ? WHERE username = ?", amount_to_pay, username)
        self.db.execute(
            "INSERT INTO history (user_id, ticker, company_name, shares, price, total, date) VALUES (?, ?, ?, ?, ?, "
            "?, ?)",
            user_id,
            ticker.upper(),
            lookup(ticker)["name"],
            amount,
            float(lookup(ticker)["price"]),
            amount_to_pay,
            date
            )
        return redirect("/")

    def other_purchases(self, username: list, user_id, ticker, amount, date):
        """
        Query database when share that user wants to buy is already owned by him
        Updates cash left, inserts holdings and history data
        """
        amount_to_pay = float(amount) * lookup(ticker)["price"]
        self.db.execute("UPDATE holdings SET shares = shares + ? WHERE ticker = ?", int(amount), ticker)
        self.db.execute("UPDATE users SET cash = cash - ? WHERE username = ?", amount_to_pay, username)
        self.db.execute("""INSERT INTO history (user_id, ticker, company_name, shares, price, total, date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        user_id,
                        ticker.upper(),
                        lookup(ticker)["name"],
                        amount,
                        float(lookup(ticker)["price"]),
                        amount_to_pay,
                        date
                        )
        return redirect("/")

    def sell_stocks(self, username, user_db_id, ticker, amount, to_pay, to_gain, date):
        """Query database to update holdings data and inserts a transaction into history"""

        self.db.execute("UPDATE users SET cash = cash + ? WHERE username = ?",
                        to_gain, username)
        self.db.execute("UPDATE holdings SET shares = shares - ? WHERE ticker = ?",
                        int(amount), ticker)
        check_dict = self.db.execute("SELECT * FROM holdings WHERE user_id = ? and ticker = ?", user_db_id, ticker)

        if check_dict[0]["shares"] == 0:
            self.db.execute("DELETE FROM holdings WHERE user_id = ? AND ticker = ?", user_db_id, ticker)

        self.db.execute("""INSERT INTO history (user_id, ticker, company_name, shares, price, total, date)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        user_db_id,
                        ticker.upper(),
                        lookup(ticker)["name"],
                        f"-{amount}",
                        float(lookup(ticker)["price"]),
                        to_pay,
                        date
                        )
        return redirect("/")

    def show_history(self, user_id):
        """Returns history of transactions table"""

        holdings_inf = self.db.execute("""SELECT ticker, company_name, shares, price, date
                                        FROM history
                                        WHERE user_id = ?
                                        ORDER BY date DESC""",
                                       user_id
                                       )

        if len(holdings_inf) == 0:
            render_template("history.html")
        return render_template("history.html", data=holdings_inf)
