#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author se4rch3r
@version 1.0
Telegram bot for removing read-only users from group.
https://github.com/se4rch3r/AntiReadOnly
"""
import datetime
import threading
import time
import os
import sqlite3

import telebot
import schedule
import telethon
from telethon import TelegramClient
from telethon.tl.types import InputChannel, InputPeerUser, ChannelParticipantsRecent
from telethon.tl.functions.contacts import ResolveUsernameRequest
from telethon.tl.functions.channels import GetParticipantsRequest

# Telethon settings
# You can get api_id, api_hash on my.telegram.org.
api_id = 0
api_hash = "<api_hash>"
telethon_account = "+749913372281"
client = TelegramClient('session_id', api_id, api_hash)
client.connect()

# Bot settings
token = "<botapi_token>"
bot_id = token.split(":")[0] 
chat_username = "<group_username>"
sorry_message = "Hello, {}! You were excluded from the conversation due to {} daytime inactivity. If you still want to be in the group, come back: @{}. You can here apply for disabling auto-kick you."
admin_id = <admin_id>
time_by = 1 # days
bot = telebot.TeleBot(token)

while not client.is_user_authorized():
    client.send_code_request(telethon_account)
    bot.send_message(admin_id, "Read-only filtering bot waiting authorization. Enter confirmation code in bot console.") # TODO: Make less security by entering code in bot
    client.sign_in(telethon_account, input("CODE: "))

# Chat id
chat_id = client(ResolveUsernameRequest(chat_username)).peer.channel_id

if not os.path.isfile("messages.db"):
    conn = sqlite3.connect('messages.db', check_same_thread=False, timeout=2)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE messages (id INTEGER PRIMARY KEY, last_date DATETIME, ignore BOOL)')
    conn.commit()
    print("[i] Create database.")
else:
    conn = sqlite3.connect('messages.db', check_same_thread=False, timeout=2)
    cursor = conn.cursor()

def bot_chat_id(chat_id):
    return int("-100" + str(chat_id))

def check_chat(message):
    if hasattr(message, "chat"):
        if message.chat.id != bot_chat_id(chat_id):
            print("Unknow chat: " + message.chat.id)
            return True
        else:
            return False


def get_users(group_username):
    users_list = []
    channel = client(ResolveUsernameRequest(group_username))
    offset_counter = 0
    while True:
        users = client(GetParticipantsRequest(InputChannel(channel.peer.channel_id, channel.chats[0].access_hash), limit=200, offset=offset_counter, filter=ChannelParticipantsRecent()))
        if len(users.participants) == 0: break
        offset_counter += 200
        users_list.extend(users.users)
        time.sleep(5)
    return users_list


@bot.message_handler(content_types=["text"])
def update(message):
    """
    Main function for registering users activity
    """
    if check_chat(message): return
    cursor.execute("REPLACE INTO messages (id, last_date) VALUES({0}, datetime('NOW', 'localtime'))".format(message.from_user.id))
    conn.commit()


def validate():
    """
    Function for kicking all read-only users
    """
    members_objects = {}
    for i in get_users(chat_username):
        members_objects[i.id] = i

    cursor.execute("SELECT * FROM messages")
    for i in cursor.fetchall():
        if (datetime.datetime.strptime(i[1], "%Y-%m-%d %H:%M:%S") + datetime.timedelta(time_by)) < datetime.datetime.now():
            if i[2] == 1: # If VIP
                print("[!] VIP USER WITH ID " + str(i[0]) + ". Ignoring.")
                continue
            if i[0] == bot_id: # If this bot.
                print("[LOL] It's me!")
                continue
            print("User with id " + str(i[0]) + " read only. Kicking.")
            if i[0] in members_objects:
                client.send_message(InputPeerUser(i[0], members_objects[i[0]].access_hash), sorry_message.format(members_objects[i[0]].first_name, time_by, chat_username))
            else:
                print("[i] User with id " + str(i[0]) + " already exited. Removing from db")
                cursor.execute("DELETE FROM messages WHERE id = {}".format(i[0]))
                conn.commit()

            try:
                bot.kick_chat_member(bot_chat_id(chat_id), i[0])
                bot.unban_chat_member(bot_chat_id(chat_id), i[0])
            except Exception as e :
                print("[!] Error on kicking user: " + str(e))
                if "administator" in repr(e):
                    cursor.execute("UPDATE FROM messages (ignore) VALUES (1) WHERE id = {}".format(i[0]))
                    conn.commit()
                else:
                    print(repr(e))
                    input("Press any key to continue execution...")
                time.sleep(2)
            else:
                cursor.execute("DELETE FROM messages WHERE id = {}".format(i[0]))
                conn.commit()
            time.sleep(5)

def validate_loop():
    """
    Schedule loop, need for schedule module
    """
    while True:
        schedule.run_pending()
        time.sleep(1)

def main():
    ############################################
    print("# CREATED BY @se4rch3r 15.08.2017 #")
    ############################################

    # Database updating
    cursor.execute("SELECT * FROM messages")
    members_database = cursor.fetchall()
    members_count = bot.get_chat_members_count(bot_chat_id(chat_id)) 
    
    if members_count > len(members_database):
        print("[i] Initializing database updating... Database length: " + str(len(members_database)))
        print("[i] Setting last_date to " + datetime.datetime.now().strftime("%Y-%m-%d %H:%I:%S"))

        cursor.execute('SELECT id FROM messages')
        database = []
        for i in cursor.fetchall():
            database.append(i[0])

        for i in get_users(chat_username):
            if not i.id in database:
                print("Adding user with id " + str(i.id))
                cursor.execute("INSERT INTO messages (id, last_date) VALUES ({}, datetime('NOW', 'localtime'))".format(i.id))
        conn.commit()
    elif members_count < len(members_database):
        print("[!] Corrupt! Need removing ghost users..")

        members_objects = {}
        for i in get_users(chat_username):
            members_objects[i.id] = i

        cursor.execute("SELECT * FROM messages")
        for i in cursor.fetchall():
            if not i[0] in members_objects:
                print("[i] Detected ghost user with id " + str(i[0]) + ". Removing from db...")
                cursor.execute("DELETE FROM messages WHERE id = {}".format(i[0]))
                conn.commit()

    print("[i] Started scheduler")
    schedule.every().hour.do(validate)
    cursor.execute("SELECT * FROM messages")
    thread = threading.Thread(target=validate_loop)
    thread.start()

    print("[i] Starting polling")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(e)

if __name__ == '__main__':
    main()
