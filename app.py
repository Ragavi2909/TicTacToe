from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3

app = Flask(__name__)
app.secret_key = "secret_key"  # Needed for session management

# Database initialization
def init_db():
    conn = sqlite3.connect("tic_tac_toe.db")
    c = conn.cursor()
    # Create users table for signup/login
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)
    # Drop the old leaderboard table if it exists (since we're changing the schema)
    c.execute("DROP TABLE IF EXISTS leaderboard")
    # Create new leaderboard table with username association
    c.execute("""
        CREATE TABLE leaderboard (
            username TEXT,
            player_name TEXT,
            wins INTEGER DEFAULT 0,
            PRIMARY KEY (username, player_name)
        )
    """)
    conn.commit()
    conn.close()

# Helper function to get a database connection
def get_db_connection():
    conn = sqlite3.connect("tic_tac_toe.db")
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

# Initialize the database when the app starts
init_db()

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("mode_select"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session["username"] = username
            return redirect(url_for("mode_select"))
        else:
            flash("Invalid username or password")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        c = conn.cursor()
        # Check if username already exists
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        if c.fetchone():
            conn.close()
            flash("Username already exists")
            return redirect(url_for("signup"))
        # Insert new user into the database
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        flash("Signup successful! Please login.")
        return redirect(url_for("login"))
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("login"))

@app.route("/mode_select")
def mode_select():
    if "username" not in session:
        return redirect(url_for("login"))
    # Clear game-specific session data when returning to mode select
    session.pop("mode", None)
    session.pop("size", None)
    session.pop("player1", None)
    session.pop("player2", None)
    return render_template("mode_select.html", username=session.get("username"))

@app.route("/player-setup", methods=["GET", "POST"])
def player_setup():
    if "username" not in session:
        return redirect(url_for("login"))

    if request.method == "GET":
        # On refresh (GET request), redirect to mode_select
        return redirect(url_for("mode_select"))

    # Handle POST request from mode_select.html
    mode = request.form["mode"]
    size = int(request.form.get("size", 3))
    if mode != "grid":
        size = 3
    session["mode"] = mode
    session["size"] = size
    return render_template("player_input.html", mode=mode, size=size, username=session.get("username"))

@app.route("/game", methods=["POST"])
def game():
    if "username" not in session:
        return redirect(url_for("login"))

    player1 = request.form.get("player1")
    player2 = request.form.get("player2", "Computer")
    mode = session.get("mode")
    size = session.get("size")

    # If any required session data is missing, redirect to mode_select
    if not all([player1, mode, size]):
        return redirect(url_for("mode_select"))

    session["player1"] = player1
    session["player2"] = player2
    session["mode"] = mode
    session["size"] = size

    # Initialize leaderboard entries for player1 and player2 under the logged-in user
    username = session["username"]
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO leaderboard (username, player_name, wins) VALUES (?, ?, 0)", (username, player1))
    if player2 != "Computer":
        c.execute("INSERT OR IGNORE INTO leaderboard (username, player_name, wins) VALUES (?, ?, 0)", (username, player2))
    conn.commit()
    conn.close()

    # Redirect to a GET route to avoid form resubmission on refresh
    return redirect(url_for("play_game"))

@app.route("/play-game", methods=["GET"])
def play_game():
    if "username" not in session:
        return redirect(url_for("login"))

    # Retrieve game data from session
    player1 = session.get("player1")
    player2 = session.get("player2")
    mode = session.get("mode")
    size = session.get("size")

    # If any required session data is missing, redirect to mode_select
    if not all([player1, player2, mode, size]):
        return redirect(url_for("mode_select"))

    return render_template("game.html", player1=player1, player2=player2, mode=mode, size=size, username=session.get("username"))

@app.route("/update-leaderboard", methods=["POST"])
def update_leaderboard():
    winner = request.form.get("winner")
    player1 = session.get("player1")
    player2 = session.get("player2")
    username = session.get("username")
    
    if winner:
        conn = get_db_connection()
        c = conn.cursor()
        if winner == player1:
            c.execute("UPDATE leaderboard SET wins = wins + 1 WHERE username = ? AND player_name = ?", (username, player1))
        elif winner == player2 and player2 != "Computer":
            c.execute("UPDATE leaderboard SET wins = wins + 1 WHERE username = ? AND player_name = ?", (username, player2))
        conn.commit()
        conn.close()
        return "Leaderboard updated", 200
    return "No update", 200

@app.route("/leaderboard")
def show_leaderboard():
    if "username" not in session:
        return redirect(url_for("login"))
    username = session.get("username")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT player_name, wins FROM leaderboard WHERE username = ? ORDER BY wins DESC", (username,))
    sorted_leaderboard = c.fetchall()
    conn.close()
    return render_template("leaderboard.html", leaderboard=sorted_leaderboard, username=session.get("username"))

@app.route("/restart")
def restart():
    if "username" not in session:
        return redirect(url_for("login"))
    # Clear game-specific session data
    session.pop("mode", None)
    session.pop("size", None)
    session.pop("player1", None)
    session.pop("player2", None)
    return redirect(url_for("mode_select"))

@app.route("/clear-session", methods=["POST"])
def clear_session():
    if "username" not in session:
        return "Not logged in", 401
    # Clear game-specific session data
    session.pop("mode", None)
    session.pop("size", None)
    session.pop("player1", None)
    session.pop("player2", None)
    return "Session cleared", 200

if __name__ == "__main__":
    app.run(debug=True)