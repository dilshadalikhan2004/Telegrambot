import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime, timedelta
import pytz
import razorpay

# Set your bot token here
bot = telebot.TeleBot('7525490429:AAG2PXrvnKS3Fd1KF999XhES_2cNljZ95dA')

# Set Indian timezone
india_tz = pytz.timezone('Asia/Kolkata')

# Connect to the SQLite database (or create it)
conn = sqlite3.connect('tickets.db', check_same_thread=False)
cursor = conn.cursor()

# Check if the payment_id column exists, and add it if it doesn't
try:
    cursor.execute("PRAGMA table_info(tickets)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'payment_id' not in columns:
        cursor.execute('ALTER TABLE tickets ADD COLUMN payment_id TEXT')
        conn.commit()
except sqlite3.OperationalError as e:
    print(f"Error checking or altering table: {e}")

# Alternatively, drop and recreate the tickets table (uncomment if you prefer this approach)
# cursor.execute('DROP TABLE IF EXISTS tickets')
# conn.commit()

# cursor.execute('''
# CREATE TABLE IF NOT EXISTS tickets (
#     ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
#     user_id INTEGER,
#     visit_date TEXT,
#     expiration_time TEXT,
#     payment_id TEXT
# )
# ''')
# conn.commit()

# Create the users table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT
)
''')
conn.commit()

# Razorpay client setup
razorpay_client = razorpay.Client(auth=("rzp_test_LoFPJBZ53pNKU5", "ceECCpyBbOYkiH3CGeFf9tmI"))

# City and Museum Data
cities = {
    "New Delhi": ["National Museum", "Crafts Museum","Rail Museum"],
    "Mumbai": ["Chhatrapati Shivaji Maharaj Vastu Sangrahalaya", "Dr. Bhau Daji Lad Museum"],
    "Kolkata": ["Indian Museum", "Victoria Memorial"],
    "Chennai": ["Government Museum", "Fort St. George Museum"],
    "Jaipur":["Albert Hall Museum","City Palace Museum"],
    "Amritsar":["Partition Museum"],
    "Udaipur":["City Palace","Vintage And Classic Car Museum"],
    "Jammu":["Dogra Art Museum"],
    "Mysore":["Folklore Museum"],
    "Hyderabad":["Salar Jung Museum"],
}

# Function to display the main menu with buttons
def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
   # start_btn = KeyboardButton('/start')
    book_btn = KeyboardButton('/book')
    cancel_btn = KeyboardButton('/cancel')
    issue_btn = KeyboardButton('/issue')
   
    markup.add( book_btn, issue_btn, cancel_btn)
    return markup

@bot.message_handler(commands=['start'])
def send_welcome(message):
    # Store user information
    cursor.execute('''
    INSERT OR IGNORE INTO users (user_id, username, first_name, last_name)
    VALUES (?, ?, ?, ?)
    ''', (message.from_user.id, message.from_user.username, message.from_user.first_name, message.from_user.last_name))
    conn.commit()

    bot.send_message(message.chat.id, "Welcome to Lyra, Your Personal Museum Reservation Bot! Please choose an option:", reply_markup=main_menu())

def select_ticket_quantity_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    quantities = [str(i) for i in range(1, 11)]  # Allow selection of up to 10 tickets
    buttons = [InlineKeyboardButton(qty, callback_data=f"qty_{qty}") for qty in quantities]
    markup.add(*buttons)
    return markup

# Function to display city selection
def select_city_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(city, callback_data=f"city_{city}") for city in cities.keys()]
    markup.add(*buttons)
    return markup

# Function to display museum selection based on selected city
def select_museum_menu(city):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(museum, callback_data=f"museum_{museum}") for museum in cities[city]]
    markup.add(*buttons)
    return markup

# Function to display available dates
def select_date_menu():
    markup = InlineKeyboardMarkup(row_width=3)
    today = datetime.now(india_tz)
    dates = [(today + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
    buttons = [InlineKeyboardButton(date, callback_data=date) for date in dates]
    markup.add(*buttons)
    return markup

# Function to display available times
def select_time_menu(date_selected):
    markup = InlineKeyboardMarkup(row_width=3)
    times = [f"{hour:02d}:00" for hour in range(8, 18)]  # Available times from 08:00 to 17:00
    buttons = [InlineKeyboardButton(time, callback_data=f"{date_selected} {time}") for time in times]
    markup.add(*buttons)
    return markup

@bot.message_handler(commands=['book'])
def handle_book(message):
    bot.send_message(message.chat.id, "Please select the city you want to visit:", reply_markup=select_city_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        if call.data.startswith("city_"):  # City selected
            selected_city = call.data.split("_")[1]
            bot.send_message(call.message.chat.id, f"You selected {selected_city}. Now choose the museum:", reply_markup=select_museum_menu(selected_city))
        
        elif call.data.startswith("museum_"):  # Museum selected
            selected_museum = call.data.split("_")[1]
            bot.send_message(call.message.chat.id, f"You selected {selected_museum}. Now choose the date:", reply_markup=select_date_menu())
        
        elif " " in call.data:  # Date and Time selected
            user_id = call.from_user.id
            visit_date = india_tz.localize(datetime.strptime(call.data, '%Y-%m-%d %H:%M'))
            expiration_time = visit_date + timedelta(hours=24)

            # Create Razorpay order
            order_amount = 10000  # Amount in paisa (i.e., ₹100)
            order_currency = 'INR'
            order_receipt = f'receipt_{user_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}'
            order = razorpay_client.order.create(dict(amount=order_amount, currency=order_currency, receipt=order_receipt))

            # Store the ticket in the database
            cursor.execute('''
            INSERT INTO tickets (user_id, visit_date, expiration_time, payment_id)
            VALUES (?, ?, ?, ?)
            ''', (user_id, visit_date.strftime('%Y-%m-%d %H:%M:%S'), expiration_time.strftime('%Y-%m-%d %H:%M:%S'), order['id']))
            conn.commit()

            bot.send_message(call.message.chat.id, f"Booking confirmed for {call.data}. Please proceed to payment: https://rzp.io/i/{order['id']}")
        else:  # Date selected
            bot.send_message(call.message.chat.id, "Please select the time slot:", reply_markup=select_time_menu(call.data))

@bot.message_handler(commands=['cancel'])
def handle_cancel(message):
    user_id = message.from_user.id
    cursor.execute('DELETE FROM tickets WHERE user_id = ? AND expiration_time > ?', (user_id, datetime.now(india_tz).strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    bot.send_message(message.chat.id, "Your reservation has been canceled.")

@bot.message_handler(commands=['issue'])
def handle_issue(message):
    bot.send_message(message.chat.id, "If you have any issues, please contact support at dillubro123@gmail.com")

# Function to clean up expired tickets (can be scheduled to run periodically)
def clean_up_expired_tickets():
    try:
        now = datetime.now(india_tz).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('DELETE FROM tickets WHERE expiration_time < ?', (now,))
        conn.commit()
    except Exception as e:
        print(f"Error in clean_up_expired_tickets: {e}")

# Function to handle Razorpay webhook for payment verification
def handle_payment_verification(payment_id, order_id):
    try:
        # Fetch the payment status using Razorpay API
        payment = razorpay_client.payment.fetch(payment_id)
        if payment['status'] == 'captured':
            # Update ticket status in the database to 'paid'
            cursor.execute('UPDATE tickets SET payment_status = ? WHERE payment_id = ?', ('paid', order_id))
            conn.commit()
            return True
        else:
            return False
    except Exception as e:
        print(f"Error in payment verification: {e}")
        return False

if __name__ == "__main__":
    # Start the bot
    bot.infinity_polling()
