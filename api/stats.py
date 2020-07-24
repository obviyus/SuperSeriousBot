def load():
	from pickle import load
	stats_dict = {}
	stats_db = open('api/stats.db', 'rb')
	try:
		stats_dict = load(stats_db)
		return stats_dict
	except:
		return {}

stats_dict = load()

def clear(update, job_queue):
	global stats_dict
	stats_dict = {}
	print("cleared")

def stats_check(update, context):
	global stats_dict
	#from global_stats import global_stats_dict
	from time import gmtime, strftime

	msg = update.message
	user = msg.from_user.id
	chat_id = update.message.chat_id
	user_object = msg.from_user

	increment(stats_dict, chat_id, user_object)
	#increment(global_stats_dict, chat_id, user_object)

	from pickle import dump
	stats_db = open('api/stats.db', 'wb')
	dump(stats_dict, stats_db)
	stats_db.close()

	#global_stats_db = open('global_stats.db','wb')
	#dump(global_stats_dict, global_stats_db)
	#global_stats_db.close()

def increment(stats_dict, chat_id, user_object):
	from time import gmtime, strftime

	if chat_id not in stats_dict.keys():
		stats_dict[chat_id] = {}
		stats_dict[chat_id]['generated'] = strftime('%d-%m-%Y', gmtime())

	if user_object not in stats_dict[chat_id]:
		stats_dict[chat_id][user_object] = 1

	else:
		stats_dict[chat_id][user_object] += 1

def dict_sort(stats_dict, chat_id):
	
	copy_dict = stats_dict 
	try:
		del copy_dict[chat_id]['generated']
	except:
		pass

	keys = list(copy_dict[chat_id].keys())
	values = list(copy_dict[chat_id].values())
	values.sort(reverse = True)

	key_list = [] 
	value_list = []
	used_list = []

	for value in values:
		for key in keys:
			if key != 'generated' and key not in used_list:
				if copy_dict[chat_id][key] == value:
					key_list.append(key)
					value_list.append(value)
					used_list.append(key)
	return key_list, value_list

def stats(update, context):
	global stats_dict
	msg = update.message
	chat_id = msg.chat_id
	chat_title = msg.chat.title

	if chat_id in stats_dict.keys():
		text = f'Stats for {chat_title} \n'
		user_list, value_list = dict_sort(stats_dict, chat_id)

		total_messages = 0
		for user in user_list:
			total_messages = total_messages + stats_dict[chat_id][user]

		for index, user in enumerate(user_list, 0):
			percentage = round((value_list[index]/total_messages)*100, 2)
			text += f'_{user.first_name} - {percentage}%_\n'
			
			if index == 9:
				break

		text = text + f'\nTotal messages - {total_messages}'
		msg.reply_text(text = text)
	else:
		msg.reply_text(text = 'No messages here')

def time_until_12():
	from time import gmtime, strftime

	a = strftime("%Y-%m-%d %H:%M:%S", gmtime())
	time = (a.split(" ",1)[1].split(":",2))
	totaltime = int(time[0])*3600+int(time[1])*60+int(time[2])+5*3600+30*60 
	totaltime = 86400 - totaltime
	return totaltime