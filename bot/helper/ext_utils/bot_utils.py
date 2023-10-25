from re import match as re_match, findall as re_findall
from threading import Thread, Event
from time import time
from math import ceil
from html import escape
from psutil import virtual_memory, cpu_percent, disk_usage
from requests import head as rhead
from urllib.request import urlopen

from bot.helper.telegram_helper.bot_commands import BotCommands
from bot import FINISHED_PROGRESS_STR, UN_FINISHED_PROGRESS_STR, download_dict, download_dict_lock, STATUS_LIMIT, botStartTime, DOWNLOAD_DIR, WEB_PINCODE, BASE_URL, EMOJI_THEME, TOTAL_TASKS_LIMIT, USER_TASKS_LIMIT, LEECH_LIMIT, MEGA_LIMIT, CREDIT_NAME, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT
from bot.helper.telegram_helper.button_build import ButtonMaker

import shutil
import psutil
from telegram.error import RetryAfter
from telegram.ext import CallbackQueryHandler
from telegram.message import Message
from telegram.update import Update
from bot import *

MAGNET_REGEX = r"magnet:\?xt=urn:btih:[a-zA-Z0-9]*"

URL_REGEX = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+"

COUNT = 0
PAGE_NO = 1
PAGES = 0


class MirrorStatus:
    if EMOJI_THEME is True:
        STATUS_UPLOADING = "ᴜᴘʟᴏᴅᴇ 📥"
        STATUS_DOWNLOADING = "ᴅᴏᴡɴʟᴏᴀᴅ 📤"
        STATUS_CLONING = "ᴄʟᴏɴᴇ 🕓"
        STATUS_WAITING = "ǫᴜᴇᴜᴇ 🏷️"
        STATUS_PAUSED = "ᴘᴀᴜsᴇ 🕯️"
        STATUS_ARCHIVING = "ᴀʀᴄʜɪᴠᴇ 🥕"
        STATUS_EXTRACTING = "ᴇxᴛʀᴀᴄᴛ 🫒"
        STATUS_SPLITTING = "sᴘʟɪᴛ 🍇"
        STATUS_CHECKING = "ᴄʜᴇᴄᴋ-ᴜᴘ 🐉"
        STATUS_SEEDING = "sᴇᴇᴅ ⛈️"
    else:
        STATUS_UPLOADING = "ᴜᴘʟᴏᴅᴇ"
        STATUS_DOWNLOADING = "ᴅᴏᴡɴʟᴏᴀᴅ"
        STATUS_CLONING = "ᴄʟᴏɴᴇ"
        STATUS_WAITING = "ǫᴜᴇᴜᴇ"
        STATUS_PAUSED = "ᴘᴀᴜsᴇ"
        STATUS_ARCHIVING = "ᴀʀᴄʜɪᴠᴇ"
        STATUS_EXTRACTING = "ᴇxᴛʀᴀᴄᴛ"
        STATUS_SPLITTING = "sᴘʟɪᴛ"
        STATUS_CHECKING = "ᴄʜᴇᴄᴋ-ᴜᴘ"
        STATUS_SEEDING = "sᴇᴇᴅ"

class EngineStatus:
    STATUS_ARIA = "ᴀʀɪᴀ2ᴄ 📶"
    STATUS_GD = "ɢᴏᴏɢʟᴇ ᴀᴘɪ ♻️"
    STATUS_MEGA = "ᴍᴇɢᴀ-sᴅᴋ ⭕️"
    STATUS_QB = "ǫʙɪᴛᴛᴏʀʀᴇɴᴛ 🦠"
    STATUS_TG = "ᴘʏʀᴏɢʀᴀᴍ 💥"
    STATUS_YT = "ʏᴛ-ᴅʟᴘ 🌟"
    STATUS_EXT = "ᴇxᴛʀᴀᴄᴛ|ᴘᴇxᴛʀᴀᴄᴛ ⚔️"
    STATUS_SPLIT = "ғғᴍᴘᴇɢ✂️"
    STATUS_ZIP = "ᴘ7ᴢɪᴘᴘ 🛠"

    
SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = Event()
        thread = Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time() + self.interval
        while not self.stopEvent.wait(nextTime - time()):
            nextTime += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()

def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'

def getDownloadByGid(gid):
    with download_dict_lock:
        for dl in list(download_dict.values()):
            if dl.gid() == gid:
                return dl
    return None

def getAllDownload(req_status: str):
    with download_dict_lock:
        for dl in list(download_dict.values()):
            status = dl.status()
            if req_status in ['all', status]:
                return dl
    return None

def bt_selection_buttons(id_: str):
    if len(id_) > 20:
        gid = id_[:12]
    else:
        gid = id_

    pincode = ""
    for n in id_:
        if n.isdigit():
            pincode += str(n)
        if len(pincode) == 4:
            break

    buttons = ButtonMaker()
    if WEB_PINCODE:
        buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{id_}")
        buttons.sbutton("Pincode", f"btsel pin {gid} {pincode}")
    else:
        buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{id_}?pin_code={pincode}")
    buttons.sbutton("Done Selecting", f"btsel done {gid} {id_}")
    return buttons.build_menu(2)


def get_user_task(user_id):
    user_task = 0
    for task in list(download_dict.values()):
        userid = task.message.from_user.id
        if userid == user_id: user_task += 1
    return user_task

def timeformatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + " days, ") if days else "") + \
        ((str(hours) + " hours, ") if hours else "") + \
        ((str(minutes) + " min, ") if minutes else "") + \
        ((str(seconds) + " sec, ") if seconds else "") + \
        ((str(milliseconds) + " millisec, ") if milliseconds else "")
    return tmp[:-2]


def get_progress_bar_string(status):
    completed = status.processed_bytes() / 8
    total = status.size_raw() / 8
    p = 0 if total == 0 else round(completed * 100 / total)
    p = min(max(p, 0), 100)
    cFull = p // 8
    p_str = FINISHED_PROGRESS_STR * cFull
    p_str += UN_FINISHED_PROGRESS_STR  * (12 - cFull)
    p_str = f"[{p_str}]"
    return p_str


def get_readable_message():
    with download_dict_lock:
        msg = f""
        if STATUS_LIMIT is not None:
            tasks = len(download_dict)
            global pages
            globals()['PAGES'] = ceil(tasks/STATUS_LIMIT)
            if PAGE_NO > PAGES and PAGES != 0:
                globals()['COUNT'] -= STATUS_LIMIT
                globals()['PAGE_NO'] -= 1
        for index, download in enumerate(list(download_dict.values())[COUNT:], start=1):
            msg += f"<b><u>ғɪʟᴇ ɴᴀᴍᴇ »</u></b>"
            msg += f" <code>{escape(str(download.name()))}</code>"
            msg += f"\n\n<b>╭───────᛬ <a href='{download.message.link}'>{download.status()}</a> ᛬──────╮</b>"
            #msg += f"<code>{escape(str(download.name()))}</code>"
            if download.status() not in [MirrorStatus.STATUS_SEEDING, MirrorStatus.STATUS_SPLITTING]:
                if EMOJI_THEME is True:
                    msg += f"\n<b>├╼ </b>{get_progress_bar_string(download)} {download.progress()}"
                    msg += f"\n<b>├╼ ᴘʀᴏᴄᴇss:</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                    msg += f"\n<b>├╼ sᴘᴇᴇᴅ:</b> {download.speed()}"
                    msg += f"\n<b>├╼ ᴇᴛᴀ:</b> {download.eta()}"
                    msg += f"<b> | ᴇʟᴀᴘsᴇᴅ: </b>{get_readable_time(time() - download.message.date.timestamp())}"
                    msg += f"\n<b>├╼ ᴇɴɢɪɴᴇ :</b> {download.eng()}"

                else:
                    msg += f"\n<b>├╼ </b>{get_progress_bar_string(download)} {download.progress()}"
                    msg += f"\n<b>├╼ ᴘʀᴏᴄᴇss:</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                    msg += f"\n<b>├╼ sᴘᴇᴇᴅ:</b> {download.speed()}"
                    msg += f"\n<b>├╼ ᴇᴛᴀ:</b> {download.eta()}"
                    msg += f"<b> | ᴇʟᴀᴘsᴇᴅ: </b>{get_readable_time(time() - download.message.date.timestamp())}"
                    msg += f"\n<b>├╼ ᴇɴɢɪɴᴇ :</b> {download.eng()}"

                if hasattr(download, 'seeders_num'):
                    try:
                        if EMOJI_THEME is True:
                            msg += f"\n<b>├╼ sᴇᴇᴅᴇʀs :</b> {download.seeders_num()} | <b>ʟᴇᴇᴄʜᴇʀs:</b> {download.leechers_num()}"
                            # msg += f"\n<b>├╼ ᴛᴏ sᴇʟᴀᴄᴛ :</b> <code>/{BotCommands.BtSelectCommand} {download.gid()}</code>"
                        else:
                            msg += f"\n<b>├╼ sᴇᴇᴅᴇʀs :</b> {download.seeders_num()} | <b>ʟᴇᴇᴄʜᴇʀs:</b> {download.leechers_num()}"
                            # msg += f"\n<b>├╼ ᴛᴏ sᴇʟᴀᴄᴛ :</b> <code>/{BotCommands.BtSelectCommand} {download.gid()}</code>"
                    except:
                        pass
                if download.message.chat.type != 'private':
                    try:
                        chatid = str(download.message.chat.id)[4:]
                        if EMOJI_THEME is True:
                            msg += f'\n<b>├╼ sᴏᴜʀᴄᴇ : </b><a href="https://t.me/c/{chatid}/{download.message.message_id}">{download.message.from_user.first_name}</a> | <b>Id :</b> <code>{download.message.from_user.id}</code>'
                            msg += f"\n<b>├╼ </b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n<b>╰─────────────────────╯</b>"
                        else:
                            msg += f'\n<b>├╼ sᴏᴜʀᴄᴇ : </b><a href="https://t.me/c/{chatid}/{download.message.message_id}">{download.message.from_user.first_name}</a> | <b>Id :</b> <code>{download.message.from_user.id}</code>'
                            msg += f"\n<b>├╼ </b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n<b>╰─────────────────────╯</b>"                 
                    except:
                        pass
                else:
                    if EMOJI_THEME is True:
                        msg += f'\n<b>├╼ ᴜsᴇʀ :</b> ️<code>{download.message.from_user.first_name}</code> | <b>Id:</b> <code>{download.message.from_user.id}</code>'
                        msg += f"\n<b>├╼ </b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n<b>╰─────────────────────╯</b>"
                    else:
                        msg += f'\n<b>├╼ ᴜsᴇʀ :</b> ️<code>{download.message.from_user.first_name}</code> | <b>Id:</b> <code>{download.message.from_user.id}</code>'
                        msg += f"\n<b>├╼ </b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n<b>╰─────────────────────╯</b>"

            elif download.status() == MirrorStatus.STATUS_SEEDING:
                if EMOJI_THEME is True:
                    msg += f"\n<b>├╼ sɪᴢᴇ: </b>{download.size()}"
                    msg += f"\n<b>├╼ ᴇɴɢɪɴᴇ:</b> <code>qBittorrent v4.4.2</code>"
                    msg += f"\n<b>├╼ sᴘᴇᴇᴅ: </b>{download.upload_speed()}"
                    msg += f"\n<b>├╼ ᴜᴘʟᴏᴀᴅᴇᴅ: </b>{download.uploaded_bytes()}"
                    msg += f"\n<b>├╼ ʀᴀᴛɪᴏ: </b>{download.ratio()}"
                    msg += f" | <b> ᴛɪᴍᴇ: </b>{download.seeding_time()}"
                    msg += f"\n<b>├╼ ᴇʟᴀᴘsᴇᴅ: </b>{get_readable_time(time() - download.message.date.timestamp())}"
                    msg += f"\n<b>├╼ </b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n<b>╰─────────────────────╯</b>"
                else:
                    msg += f"\n<b>├╼ sɪᴢᴇ: </b>{download.size()}"
                    msg += f"\n<b>├╼ ᴇɴɢɪɴᴇ <code>qBittorrent v4.4.2</code>"
                    msg += f"\n<b>├╼ Speed: </b>{download.upload_speed()}"
                    msg += f"\n<b>├╼ ᴜᴘʟᴏᴀᴅᴇᴅ: </b>{download.uploaded_bytes()}"
                    msg += f"\n<b>├╼ ʀᴀᴛɪᴏ: </b>{download.ratio()}"
                    msg += f" | <b> ᴛɪᴍᴇ: </b>{download.seeding_time()}"
                    msg += f"\n<b>├╼ ᴇʟᴀᴘsᴇᴅ: </b>{get_readable_time(time() - download.message.date.timestamp())}"
                    msg += f"\n<b>├╼ </b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n<b>╰─────────────────────╯</b>"
            else:
                if EMOJI_THEME is True:
                    msg += f"\n<b>├╼ ᴇɴɢɪɴᴇ:</b> {download.eng()}"
                    msg += f"\n<b>├╼ sɪᴢᴇ: </b>{download.size()}\n<b>╰─────────────────────╯</b>"
                else:
                    msg += f"\n<b>├╼ ᴇɴɢɪɴᴇ:</b> {download.eng()}"
                    msg += f"\n<b>├╼ sɪᴢᴇ: </b>{download.size()}\n<b>╰─────────────────────╯</b>"
            #msg += f"\n<b>_____________________________________</b>"
           # msg += "<b><u>ᴘᴏᴡᴇʀᴇᴅ ʙʏ</u> - <a href='https://t.me/MSXCloud'>ᴍs-x-ᴄʟᴏᴜᴅ</a></b>"
            msg += "\n\n"
            if STATUS_LIMIT is not None and index == STATUS_LIMIT:
                break
        if len(msg) == 0:
            return None, None
        dl_speed = 0
        up_speed = 0
        for download in list(download_dict.values()):
            spd = download.speed()
            if download.status() == MirrorStatus.STATUS_DOWNLOADING:
                spd = download.speed()
                if 'K' in spd:
                    dl_speed += float(spd.split('K')[0]) * 1024
                elif 'M' in spd:
                    dl_speed += float(spd.split('M')[0]) * 1048576
            elif download.status() == MirrorStatus.STATUS_UPLOADING:
                spd = download.speed()
                if 'KB/s' in spd:
                    up_speed += float(spd.split('K')[0]) * 1024
                elif 'MB/s' in spd:
                    up_speed += float(spd.split('M')[0]) * 1048576
            elif download.status() == MirrorStatus.STATUS_SEEDING:
                spd = download.upload_speed()
                if 'K' in spd:
                    up_speed += float(spd.split('K')[0]) * 1024
                elif 'M' in spd:
                    up_speed += float(spd.split('M')[0]) * 1048576
            #msg += f"<b><u>ᴘᴏᴡᴇʀᴇᴅ ʙʏ</u> - <a href='https://t.me/Hs_Botz'>ʜꜱ ᠰ ʙᴏᴛꜱ</a></b>"
        if EMOJI_THEME is True:
            bmsg = f"<b>ᴄᴘᴜ:</b> {cpu_percent()}% | <b>ғʀᴇᴇ:</b> {get_readable_file_size(disk_usage(DOWNLOAD_DIR).free)}"
            bmsg += f"\n<b>ʀᴀᴍ:</b> {virtual_memory().percent}% | <b>ᴜᴘᴛɪᴍᴇ:</b> {get_readable_time(time() - botStartTime)}"
            bmsg += f"\n<b>ᴅʟ:</b> {get_readable_file_size(dl_speed)}/s | <b>ᴜʟ:</b> {get_readable_file_size(up_speed)}/s"
            bmsg += f"\n\n"
            bmsg += f"<b><u>ᴘᴏᴡᴇʀᴇᴅ ʙʏ</u> - <a href='https://t.me/OMGxCLOUD'>ᴏᴍɢ x ᴄʟᴏᴜᴅ</a></b>"
        else:
            bmsg = f"<b>ᴄᴘᴜ:</b> {cpu_percent()}% | <b>ғʀᴇᴇ:</b> {get_readable_file_size(disk_usage(DOWNLOAD_DIR).free)}"
            bmsg += f"\n<b>ʀᴀᴍ:</b> {virtual_memory().percent}% | <b>ᴜᴘᴛɪᴍᴇ:</b> {get_readable_time(time() - botStartTime)}"
            bmsg += f"\n<b>ᴅʟ:</b> {get_readable_file_size(dl_speed)}/s | <b>ᴜʟ:</b> {get_readable_file_size(up_speed)}/s"
            bmsg += f"\n\n"
            bmsg += f"<b><u>ᴘᴏᴡᴇʀᴇᴅ ʙʏ</u> - <a href='https://t.me/OMGxCLOUD'>ᴏᴍɢ x ᴄʟᴏᴜᴅ</a></b>"
        
        buttons = ButtonMaker()
        buttons.sbutton("ʀᴇғʀᴇsʜ", "status refresh")
        buttons.sbutton("sᴛᴀᴛɪsᴛɪᴄs", str(THREE))
        buttons.sbutton("ᴄʟᴏsᴇ", "status close")
        sbutton = buttons.build_menu(3)
        
        if STATUS_LIMIT is not None and tasks > STATUS_LIMIT:
            msg += f"<b>ᴛᴀsᴋs:</b> {tasks}\n"
            buttons = ButtonMaker()
            if EMOJI_THEME is True:
                buttons.sbutton("⇇ʙᴀᴄᴋ", "status pre")
                buttons.sbutton(f"{PAGE_NO}/{PAGES}", str(THREE))
                buttons.sbutton("ɴᴇxᴛ⇉", "status nex")
                buttons.sbutton("ʀᴇғʀᴇsʜ", "status refresh")
                buttons.sbutton("ᴄʟᴏsᴇ", "status close")
            else:
                buttons.sbutton("⇇ʙᴀᴄᴋ", "status pre")
                buttons.sbutton(f"{PAGE_NO}/{PAGES}", str(THREE))
                buttons.sbutton("ɴᴇxᴛ⇉", "status nex")
                buttons.sbutton("ʀᴇғʀᴇsʜ", "status refresh")
                buttons.sbutton("ᴄʟᴏsᴇ", "status close")
            button = buttons.build_menu(3)
            return msg + bmsg, button
        return msg + bmsg, sbutton

def turn(data):
    try:
        with download_dict_lock:
            global COUNT, PAGE_NO
            if data[1] == "nex":
                if PAGE_NO == PAGES:
                    COUNT = 0
                    PAGE_NO = 1
                else:
                    COUNT += STATUS_LIMIT
                    PAGE_NO += 1
            elif data[1] == "pre":
                if PAGE_NO == 1:
                    COUNT = STATUS_LIMIT * (PAGES - 1)
                    PAGE_NO = PAGES
                else:
                    COUNT -= STATUS_LIMIT
                    PAGE_NO -= 1
        return True
    except:
        return False

def get_readable_time(seconds: int) -> str:
    result = ''
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f'{days}d'
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f'{hours}h'
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f'{minutes}m'
    seconds = int(seconds)
    result += f'{seconds}s'
    return result

def is_url(url: str):
    url = re_findall(URL_REGEX, url)
    return bool(url)

def is_gdrive_link(url: str):
    return "drive.google.com" in url

def is_gdtot_link(url: str):
    url = re_match(r'https?://.+\.gdtot\.\S+', url)
    return bool(url)

def is_unified_link(url: str):
    url = re_match(r'https?://(appdrive|driveapp|driveace|gdflix|drivebit|drivesharer|drivepro)\.\S+', url)
    if bool(url) == True:
        return bool(url)
    else:
        return False

def is_udrive_link(url: str):
    if 'drivehub.ws' in url:
        return 'drivehub.ws' in url
    else:
        url = re_match(r'https?://(hubdrive|katdrive|kolop|drivefire|drivebuzz)\.\S+', url)
        return bool(url)

def is_mega_link(url: str):
    return "mega.nz" in url or "mega.co.nz" in url

def get_mega_link_type(url: str):
    if "folder" in url:
        return "folder"
    elif "file" in url:
        return "file"
    elif "/#F!" in url:
        return "folder"
    return "file"

def is_magnet(url: str):
    magnet = re_findall(MAGNET_REGEX, url)
    return bool(magnet)

def new_thread(fn):
    """To use as decorator to make a function call threaded.
    Needs import
    from threading import Thread"""

    def wrapper(*args, **kwargs):
        thread = Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper

def get_content_type(link: str) -> str:
    try:
        res = rhead(link, allow_redirects=True, timeout=5, headers = {'user-agent': 'Wget/1.12'})
        content_type = res.headers.get('content-type')
    except:
        try:
            res = urlopen(link, timeout=5)
            info = res.info()
            content_type = info.get_content_type()
        except:
            content_type = None
    return content_type


ONE, TWO, THREE = range(3)
def pop_up_stats(update, context):
    query = update.callback_query
    stats = bot_sys_stats()
    query.answer(text=stats, show_alert=True)
def bot_sys_stats():
    currentTime = get_readable_time(time() - botStartTime)
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage(DOWNLOAD_DIR).percent
    total, used, free = shutil.disk_usage(DOWNLOAD_DIR)
    total = get_readable_file_size(total)
    used = get_readable_file_size(used)
    free = get_readable_file_size(free)
    recv = get_readable_file_size(psutil.net_io_counters().bytes_recv)
    sent = get_readable_file_size(psutil.net_io_counters().bytes_sent)
    num_active = 0
    num_upload = 0
    num_split = 0
    num_extract = 0
    num_archi = 0
    tasks = len(download_dict)
    for stats in list(download_dict.values()):
       if stats.status() == MirrorStatus.STATUS_DOWNLOADING:
                num_active += 1
       if stats.status() == MirrorStatus.STATUS_UPLOADING:
                num_upload += 1
       if stats.status() == MirrorStatus.STATUS_ARCHIVING:
                num_archi += 1
       if stats.status() == MirrorStatus.STATUS_EXTRACTING:
                num_extract += 1
       if stats.status() == MirrorStatus.STATUS_SPLITTING:
                num_split += 1
    stats = f"""
CPU : {cpu}% | RAM : {mem}%
DL : {num_active} | UP : {num_upload} | SPLIT : {num_split}
ZIP : {num_archi} | UNZIP : {num_extract} | TOTAL : {tasks}
Limits : T/D : {TORRENT_DIRECT_LIMIT}GB | Z/U : {ZIP_UNZIP_LIMIT}GB
                    L : {LEECH_LIMIT}GB | M : {MEGA_LIMIT}GB
Made with ❤️ by {CREDIT_NAME}
"""
    return stats
dispatcher.add_handler(
    CallbackQueryHandler(pop_up_stats, pattern="^" + str(THREE) + "$")
)
