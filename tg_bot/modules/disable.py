from typing import Union, List, Optional

from future.utils import string_types
from telegram import ParseMode, Update, Chat, User
from telegram.ext import CommandHandler, Filters, CallbackContext, MessageHandler
from telegram.utils.helpers import escape_markdown

from tg_bot import dispatcher
from tg_bot.modules.helper_funcs.handlers import CMD_STARTERS
from tg_bot.modules.helper_funcs.misc import is_module_loaded

FILENAME = __name__.rsplit(".", 1)[-1]

# If module is due to be loaded, then setup all the magical handlers
if is_module_loaded(FILENAME):
    from tg_bot.modules.helper_funcs.chat_status import user_admin, is_user_admin
    from telegram.ext.dispatcher import run_async

    from tg_bot.modules.sql import disable_sql as sql

    DISABLE_CMDS = []
    DISABLE_OTHER = []
    ADMIN_CMDS = []

    class DisableAbleCommandHandler(CommandHandler):
        def __init__(self, command, callback, admin_ok=False, **kwargs):
            super().__init__(command, callback, **kwargs)
            self.admin_ok = admin_ok
            if isinstance(command, string_types):
                DISABLE_CMDS.append(command)
                if admin_ok:
                    ADMIN_CMDS.append(command)
            else:
                DISABLE_CMDS.extend(command)
                if admin_ok:
                    ADMIN_CMDS.extend(command)

        def check_update(self, update):
            chat = update.effective_chat  # type: Optional[Chat]
            user = update.effective_user  # type: Optional[User]
            if super().check_update(update):
                # Should be safe since check_update passed.
                command = update.effective_message.text_html.split(None, 1)[0][1:].split('@')[0]

                # disabled, admincmd, user admin
                if sql.is_command_disabled(chat.id, command):
                    return command in ADMIN_CMDS and is_user_admin(chat, user.id)

                # not disabled
                else:
                    return True

            return False


    class DisableAbleRegexHandler(MessageHandler):
        def __init__(self, pattern, callback, friendly="", **kwargs):
            super().__init__(pattern, callback, **kwargs)
            DISABLE_OTHER.append(friendly or pattern)
            self.friendly = friendly or pattern

        def check_update(self, update):
            chat = update.effective_chat
            return super().check_update(update) and not sql.is_command_disabled(chat.id, self.friendly)


    @run_async
    @user_admin
    def disable(update: Update, context: CallbackContext):
        args = context.args
        chat = update.effective_chat  # type: Optional[Chat]
        if len(args) >= 1:
            disable_cmd = args[0]
            if disable_cmd.startswith(CMD_STARTERS):
                disable_cmd = disable_cmd[1:]

            if disable_cmd in set(DISABLE_CMDS + DISABLE_OTHER):
                sql.disable_command(chat.id, disable_cmd)
                update.effective_message.reply_text("`{}` 명령어의 사용을 비활성화합니다.".format(disable_cmd),
                                                    parse_mode=ParseMode.MARKDOWN)
            else:
                update.effective_message.reply_text("그 명령어는 비활성화하실 수 없어요.")

        else:
            update.effective_message.reply_text("비활성화할 명령어를 입력해 주세요.")


    @run_async
    @user_admin
    def enable(update: Update, context: CallbackContext):
        args = context.args
        chat = update.effective_chat  # type: Optional[Chat]
        if len(args) >= 1:
            enable_cmd = args[0]
            if enable_cmd.startswith(CMD_STARTERS):
                enable_cmd = enable_cmd[1:]

            if sql.enable_command(chat.id, enable_cmd):
                update.effective_message.reply_text("`{}` 명령어의 사용을 활성화합니다.".format(enable_cmd),
                                                    parse_mode=ParseMode.MARKDOWN)
            else:
                update.effective_message.reply_text("이미 활성화되어 있어요.")

        else:
            update.effective_message.reply_text("활성화할 명령어를 입력해 주세요.")


    @run_async
    @user_admin
    def list_cmds(update: Update, context):
        if DISABLE_CMDS + DISABLE_OTHER:
            result = ""
            for cmd in set(DISABLE_CMDS + DISABLE_OTHER):
                result += " - `{}`\n".format(escape_markdown(cmd))
            update.effective_message.reply_text("다음 명령은 전환할 수 있어요 :\n{}".format(result),
                                                parse_mode=ParseMode.MARKDOWN)
        else:
            update.effective_message.reply_text("사용하지 않도록 설정할 수 있는 명령어가 없어요.")


    # do not async
    def build_curr_disabled(chat_id: Union[str, int]) -> str:
        disabled = sql.get_all_disabled(chat_id)
        if not disabled:
            return "사용하지 않도록 설정된 명령어가 없어요!"

        result = ""
        for cmd in disabled:
            result += " - `{}`\n".format(escape_markdown(cmd))
        return "다음 명령은 현재 비활성화되어 있습니다 :\n{}".format(result)


    @run_async
    def commands(update: Update, context):
        chat = update.effective_chat
        update.effective_message.reply_text(build_curr_disabled(chat.id), parse_mode=ParseMode.MARKDOWN)


    def __stats__():
        return "{}개의 채팅방에서 {}개의 명령어가 비활성화 되었습니다.".format(sql.num_chats(), sql.num_disabled())


    def __migrate__(old_chat_id, new_chat_id):
        sql.migrate_chat(old_chat_id, new_chat_id)


    def __chat_settings__(chat_id, user_id):
        return build_curr_disabled(chat_id)


    __mod_name__ = "명령어 비활성화"

    __help__ = """
 - /cmds: 비활성화된 명령어를 확인해요.

*Admin only:*
 - /enable <명령어>: 명령어를 활성화해요.
 - /disable <명령어>: 명령어를 비활성화해요.
 - /listcmds: 사용 가능한 모든 전환 가능한 명령어를 나열해요.
    """

    DISABLE_HANDLER = CommandHandler("disable", disable, pass_args=True, filters=Filters.group)
    ENABLE_HANDLER = CommandHandler("enable", enable, pass_args=True, filters=Filters.group)
    COMMANDS_HANDLER = CommandHandler(["cmds", "disabled"], commands, filters=Filters.group)
    TOGGLE_HANDLER = CommandHandler("listcmds", list_cmds, filters=Filters.group)

    dispatcher.add_handler(DISABLE_HANDLER)
    dispatcher.add_handler(ENABLE_HANDLER)
    dispatcher.add_handler(COMMANDS_HANDLER)
    dispatcher.add_handler(TOGGLE_HANDLER)

else:
    DisableAbleCommandHandler = CommandHandler
    DisableAbleRegexHandler = MessageHandler
