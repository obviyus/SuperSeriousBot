from requests import get
import pprint
import datetime


pp = pprint.PrettyPrinter(indent=4)


def time(bot, update):
	msg = update.message

	text = msg.text.split(' ',1)

	if len(text)>1:
		place = text[1]

		key = "fe35b3d7dc4f24468b3b376776035cfd"
		url = f"http://api.openweathermap.org/data/2.5/weather?id=524901&APPID={key}&q={place}"

		response = get(url)
		data = response.json()

		if data['cod'] != "404":
			timezone = data['timezone']
			current_unix_time = datetime.datetime.utcnow().timestamp() + timezone

			full_time = (
			    datetime.datetime.fromtimestamp(
			        int(current_unix_time)
			    ).strftime('%H:%M %d-%m-%Y')
			)
			full_time = full_time.split(' ')
			time = full_time[0]
			date = full_time[1]

			hour = int(time[:2])
			if hour>12:
				hour = hour - 12
				meridiem = "pm"
			else:
				meridiem = "am"

			text = f"*{hour}{time[2:]}{meridiem}*\n_{date}_"

		else:
			text = "No entry found"
	else:
		text = "*Format*: `/time {PLACE}`\nAdd the data code for the specific country for better results."
	bot.send_message(chat_id = msg.chat_id, 
					 text = text,
					 parse_mode = 'Markdown',
					 reply_to_message_id = msg.message_id
					 )
	