from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from src.bot.keyboards.inline import MenuKeyboards
from src.services.user import UserService
from src.db.schemas.user import UserCreate

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    """РћР±СЂР°Р±РѕС‚С‡РёРє РєРѕРјР°РЅРґС‹ /start"""
    user_service = UserService(session)
    
    # РџСЂРѕРІРµСЂСЏРµРј, РµСЃС‚СЊ Р»Рё РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РІ Р‘Р”
    user = await user_service.get_by_telegram_id(message.from_user.id)
    
    if not user:
        # Р РµРіРёСЃС‚СЂР°С†РёСЏ РЅРѕРІРѕРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        user_data = UserCreate(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
            role_names=["operator"]  # РџРѕ СѓРјРѕР»С‡Р°РЅРёСЋ РѕРїРµСЂР°С‚РѕСЂ
        )
        
        try:
            user = await user_service.create_user(user_data)
            welcome_text = (
                f"рџ‘‹ Р”РѕР±СЂРѕ РїРѕР¶Р°Р»РѕРІР°С‚СЊ РІ VendHub, {message.from_user.first_name}!\n\n"
                "рџЋ‰ Р’С‹ СѓСЃРїРµС€РЅРѕ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅС‹ РІ СЃРёСЃС‚РµРјРµ.\n"
                "рџ“‹ Р’Р°Рј РЅР°Р·РЅР°С‡РµРЅР° СЂРѕР»СЊ: <b>РћРїРµСЂР°С‚РѕСЂ</b>\n\n"
                "Р”Р»СЏ РїРѕР»СѓС‡РµРЅРёСЏ РґСЂСѓРіРёС… СЂРѕР»РµР№ РѕР±СЂР°С‚РёС‚РµСЃСЊ Рє Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ."
            )
        except Exception as e:
            await message.answer(
                "вќЊ РћС€РёР±РєР° РїСЂРё СЂРµРіРёСЃС‚СЂР°С†РёРё. РћР±СЂР°С‚РёС‚РµСЃСЊ Рє Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ."
            )
            return
    else:
        # РџСЂРёРІРµС‚СЃС‚РІРёРµ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РµРіРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        roles_text = ", ".join([role.display_name or role.name for role in user.roles])
        welcome_text = (
            f"рџ‘‹ РЎ РІРѕР·РІСЂР°С‰РµРЅРёРµРј, {user.full_name}!\n\n"
            f"рџ‘¤ Р’Р°С€Рё СЂРѕР»Рё: <b>{roles_text}</b>\n"
            f"рџ“± Р’С‹Р±РµСЂРёС‚Рµ РґРµР№СЃС‚РІРёРµ РёР· РјРµРЅСЋ РЅРёР¶Рµ:"
        )
    
    # РћС‚РїСЂР°РІР»СЏРµРј РїСЂРёРІРµС‚СЃС‚РІРёРµ СЃ РіР»Р°РІРЅС‹Рј РјРµРЅСЋ
    user_roles = [role.name for role in user.roles]
    await message.answer(
        welcome_text,
        reply_markup=MenuKeyboards.main_menu(user_roles)
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, session: AsyncSession):
    """РџРѕРєР°Р·Р°С‚СЊ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(message.from_user.id)
    
    if not user:
        await message.answer(
            "вќЊ Р’С‹ РЅРµ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅС‹ РІ СЃРёСЃС‚РµРјРµ.\n"
            "РСЃРїРѕР»СЊР·СѓР№С‚Рµ /start РґР»СЏ СЂРµРіРёСЃС‚СЂР°С†РёРё."
        )
        return
    
    user_roles = [role.name for role in user.roles]
    await message.answer(
        "рџ“± Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ:",
        reply_markup=MenuKeyboards.main_menu(user_roles)
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """РџРѕРјРѕС‰СЊ РїРѕ Р±РѕС‚Сѓ"""
    help_text = """
вќ“ <b>РџРѕРјРѕС‰СЊ РїРѕ VendHub Bot</b>

<b>РћСЃРЅРѕРІРЅС‹Рµ РєРѕРјР°РЅРґС‹:</b>
/start - РќР°С‡Р°С‚СЊ СЂР°Р±РѕС‚Сѓ СЃ Р±РѕС‚РѕРј
/menu - РџРѕРєР°Р·Р°С‚СЊ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ
/profile - РњРѕР№ РїСЂРѕС„РёР»СЊ
/tasks - РњРѕРё Р·Р°РґР°С‡Рё (РґР»СЏ РѕРїРµСЂР°С‚РѕСЂРѕРІ)
/stats - РЎС‚Р°С‚РёСЃС‚РёРєР°
/settings - РќР°СЃС‚СЂРѕР№РєРё
/help - Р­С‚Р° СЃРїСЂР°РІРєР°
/cancel - РћС‚РјРµРЅРёС‚СЊ С‚РµРєСѓС‰РµРµ РґРµР№СЃС‚РІРёРµ

<b>Р РѕР»Рё РІ СЃРёСЃС‚РµРјРµ:</b>
рџ‘· <b>РћРїРµСЂР°С‚РѕСЂ</b> - РѕР±СЃР»СѓР¶РёРІР°РЅРёРµ Р°РІС‚РѕРјР°С‚РѕРІ
рџ“¦ <b>РЎРєР»Р°Рґ</b> - СѓРїСЂР°РІР»РµРЅРёРµ Р·Р°РїР°СЃР°РјРё
рџ’ј <b>РњРµРЅРµРґР¶РµСЂ</b> - СѓРїСЂР°РІР»РµРЅРёРµ Рё РѕС‚С‡РµС‚С‹
рџ’Ћ <b>РРЅРІРµСЃС‚РѕСЂ</b> - РїСЂРѕСЃРјРѕС‚СЂ РёРЅРІРµСЃС‚РёС†РёР№
вљ™пёЏ <b>РђРґРјРёРЅ</b> - РїРѕР»РЅС‹Р№ РґРѕСЃС‚СѓРї

<b>РќР°РІРёРіР°С†РёСЏ:</b>
РСЃРїРѕР»СЊР·СѓР№С‚Рµ РєРЅРѕРїРєРё РїРѕРґ СЃРѕРѕР±С‰РµРЅРёСЏРјРё РґР»СЏ РЅР°РІРёРіР°С†РёРё.
Р’ Р»СЋР±РѕР№ РјРѕРјРµРЅС‚ РјРѕР¶РµС‚Рµ РІРµСЂРЅСѓС‚СЊСЃСЏ РІ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ РєРѕРјР°РЅРґРѕР№ /menu

<b>РџРѕРґРґРµСЂР¶РєР°:</b>
РџРѕ РІСЃРµРј РІРѕРїСЂРѕСЃР°Рј РѕР±СЂР°С‰Р°Р№С‚РµСЃСЊ Рє Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.
    """
    
    await message.answer(help_text)


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, session: AsyncSession):
    """Р’РѕР·РІСЂР°С‚ РІ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ"""
    user_service = UserService(session)
    user = await user_service.get_by_telegram_id(callback.from_user.id)
    
    if not user:
        await callback.answer("Р’С‹ РЅРµ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅС‹", show_alert=True)
        return
    
    user_roles = [role.name for role in user.roles]
    await callback.message.edit_text(
        "рџ“± Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ:",
        reply_markup=MenuKeyboards.main_menu(user_roles)
    )
    await callback.answer()


@router.callback_query(F.data == "profile")
async def callback_profile(callback: CallbackQuery, session: AsyncSession):
    """РџРѕРєР°Р·Р°С‚СЊ РїСЂРѕС„РёР»СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ"""
    user_service = UserService(session)
    user = await user_service.get_user_with_stats(callback.from_user.id)
    
    if not user:
        await callback.answer("Р’С‹ РЅРµ Р·Р°СЂРµРіРёСЃС‚СЂРёСЂРѕРІР°РЅС‹", show_alert=True)
        return
    
    roles_text = ", ".join([role.display_name or role.name for role in user.roles])
    
    profile_text = f"""
рџ‘¤ <b>РњРѕР№ РїСЂРѕС„РёР»СЊ</b>

<b>РРјСЏ:</b> {user.full_name}
<b>Username:</b> @{user.username or 'РЅРµ СѓРєР°Р·Р°РЅ'}
<b>Telegram ID:</b> <code>{user.telegram_id}</code>
<b>РўРµР»РµС„РѕРЅ:</b> {user.phone or 'РЅРµ СѓРєР°Р·Р°РЅ'}
<b>Email:</b> {user.email or 'РЅРµ СѓРєР°Р·Р°РЅ'}

<b>Р РѕР»Рё:</b> {roles_text}
<b>РЎС‚Р°С‚СѓСЃ:</b> {'вњ… РђРєС‚РёРІРµРЅ' if user.is_active else 'вќЊ Р—Р°Р±Р»РѕРєРёСЂРѕРІР°РЅ'}
<b>Р’РµСЂРёС„РёРєР°С†РёСЏ:</b> {'вњ… РџРѕРґС‚РІРµСЂР¶РґРµРЅ' if user.is_verified else 'вЏі РќРµ РїРѕРґС‚РІРµСЂР¶РґРµРЅ'}

<b>рџ“Љ РЎС‚Р°С‚РёСЃС‚РёРєР°:</b>
рџЏЄ РђРІС‚РѕРјР°С‚РѕРІ РїРѕРґ СѓРїСЂР°РІР»РµРЅРёРµРј: {user.managed_machines_count}
рџ“‹ РђРєС‚РёРІРЅС‹С… Р·Р°РґР°С‡: {user.active_tasks_count}
вњ… Р’С‹РїРѕР»РЅРµРЅРѕ Р·Р°РґР°С‡: {user.completed_tasks_count}
рџ’° РЎСѓРјРјР° РёРЅРІРµСЃС‚РёС†РёР№: {user.total_investment:,.0f} UZS

<b>Р”Р°С‚Р° СЂРµРіРёСЃС‚СЂР°С†РёРё:</b> {user.created_at.strftime('%d.%m.%Y')}
    """
    
    await callback.message.edit_text(
        profile_text,
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "stats")
async def callback_stats(callback: CallbackQuery, session: AsyncSession):
    """РџРѕРєР°Р·Р°С‚СЊ РѕР±С‰СѓСЋ СЃС‚Р°С‚РёСЃС‚РёРєСѓ"""
    # TODO: Р РµР°Р»РёР·РѕРІР°С‚СЊ РїРѕР»СѓС‡РµРЅРёРµ СЃС‚Р°С‚РёСЃС‚РёРєРё
    stats_text = """
рџ“Љ <b>РћР±С‰Р°СЏ СЃС‚Р°С‚РёСЃС‚РёРєР°</b>

<b>РЎРµРіРѕРґРЅСЏ:</b>
рџ’° РџСЂРѕРґР°Р¶Рё: 1,234,567 UZS
в• Р§Р°С€РµРє РєРѕС„Рµ: 156
рџЌ« РЎРЅРµРєРѕРІ: 89
рџ“€ РЎСЂРµРґРЅРёР№ С‡РµРє: 7,900 UZS

<b>Р­С‚РѕС‚ РјРµСЃСЏС†:</b>
рџ’° РџСЂРѕРґР°Р¶Рё: 45,678,900 UZS
рџ“€ Р РѕСЃС‚ Рє РїСЂРѕС€Р»РѕРјСѓ РјРµСЃСЏС†Сѓ: +12.5%
рџЏ† Р›СѓС‡С€РёР№ Р°РІС‚РѕРјР°С‚: VM-001

<b>РћРїРµСЂР°С†РёРѕРЅРЅС‹Рµ РїРѕРєР°Р·Р°С‚РµР»Рё:</b>
вњ… Р Р°Р±РѕС‚Р°СЋС‰РёС… Р°РІС‚РѕРјР°С‚РѕРІ: 45/50
вљ пёЏ РўСЂРµР±СѓСЋС‚ РѕР±СЃР»СѓР¶РёРІР°РЅРёСЏ: 3
рџ”§ РќР° СЂРµРјРѕРЅС‚Рµ: 2

<i>РћР±РЅРѕРІР»РµРЅРѕ: {datetime.now().strftime('%H:%M')}</i>
    """
    
    await callback.message.edit_text(
        stats_text,
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "settings")
async def callback_settings(callback: CallbackQuery, session: AsyncSession):
    """РќР°СЃС‚СЂРѕР№РєРё РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ"""
    # TODO: Р РµР°Р»РёР·РѕРІР°С‚СЊ РЅР°СЃС‚СЂРѕР№РєРё
    settings_text = """
вљ™пёЏ <b>РќР°СЃС‚СЂРѕР№РєРё</b>

рџ”” <b>РЈРІРµРґРѕРјР»РµРЅРёСЏ:</b>
в”њ РќРѕРІС‹Рµ Р·Р°РґР°С‡Рё: вњ…
в”њ РћС‚С‡РµС‚С‹: вњ…
в”” РЎРёСЃС‚РµРјРЅС‹Рµ: вњ…

рџЊђ <b>РЇР·С‹Рє:</b> рџ‡·рџ‡є Р СѓСЃСЃРєРёР№

рџ•ђ <b>Р§Р°СЃРѕРІРѕР№ РїРѕСЏСЃ:</b> UTC+5 (РўР°С€РєРµРЅС‚)

рџ“± <b>РРЅС‚РµСЂС„РµР№СЃ:</b>
в”” РљРѕРјРїР°РєС‚РЅС‹Р№ СЂРµР¶РёРј: вќЊ

<i>Р¤СѓРЅРєС†РёРѕРЅР°Р» РІ СЂР°Р·СЂР°Р±РѕС‚РєРµ...</i>
    """
    
    await callback.message.edit_text(
        settings_text,
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """РџРѕРјРѕС‰СЊ С‡РµСЂРµР· callback"""
    await callback_help_handler(callback)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """РћС‚РјРµРЅР° С‚РµРєСѓС‰РµРіРѕ РґРµР№СЃС‚РІРёСЏ"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("РќРµС‡РµРіРѕ РѕС‚РјРµРЅСЏС‚СЊ.")
        return
    
    await state.clear()
    await message.answer(
        "вќЊ Р”РµР№СЃС‚РІРёРµ РѕС‚РјРµРЅРµРЅРѕ.",
        reply_markup=MenuKeyboards.back_button("main_menu")
    )


async def callback_help_handler(callback: CallbackQuery):
    """Р’СЃРїРѕРјРѕРіР°С‚РµР»СЊРЅР°СЏ С„СѓРЅРєС†РёСЏ РґР»СЏ РїРѕРєР°Р·Р° РїРѕРјРѕС‰Рё"""
    help_text = """
вќ“ <b>РџРѕРјРѕС‰СЊ РїРѕ VendHub Bot</b>

<b>РћСЃРЅРѕРІРЅС‹Рµ РєРѕРјР°РЅРґС‹:</b>
/start - РќР°С‡Р°С‚СЊ СЂР°Р±РѕС‚Сѓ СЃ Р±РѕС‚РѕРј
/menu - РџРѕРєР°Р·Р°С‚СЊ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ
/profile - РњРѕР№ РїСЂРѕС„РёР»СЊ
/tasks - РњРѕРё Р·Р°РґР°С‡Рё (РґР»СЏ РѕРїРµСЂР°С‚РѕСЂРѕРІ)
/stats - РЎС‚Р°С‚РёСЃС‚РёРєР°
/settings - РќР°СЃС‚СЂРѕР№РєРё
/help - Р­С‚Р° СЃРїСЂР°РІРєР°
/cancel - РћС‚РјРµРЅРёС‚СЊ С‚РµРєСѓС‰РµРµ РґРµР№СЃС‚РІРёРµ

<b>Р РѕР»Рё РІ СЃРёСЃС‚РµРјРµ:</b>
рџ‘· <b>РћРїРµСЂР°С‚РѕСЂ</b> - РѕР±СЃР»СѓР¶РёРІР°РЅРёРµ Р°РІС‚РѕРјР°С‚РѕРІ
рџ“¦ <b>РЎРєР»Р°Рґ</b> - СѓРїСЂР°РІР»РµРЅРёРµ Р·Р°РїР°СЃР°РјРё
рџ’ј <b>РњРµРЅРµРґР¶РµСЂ</b> - СѓРїСЂР°РІР»РµРЅРёРµ Рё РѕС‚С‡РµС‚С‹
рџ’Ћ <b>РРЅРІРµСЃС‚РѕСЂ</b> - РїСЂРѕСЃРјРѕС‚СЂ РёРЅРІРµСЃС‚РёС†РёР№
вљ™пёЏ <b>РђРґРјРёРЅ</b> - РїРѕР»РЅС‹Р№ РґРѕСЃС‚СѓРї

<b>РќР°РІРёРіР°С†РёСЏ:</b>
РСЃРїРѕР»СЊР·СѓР№С‚Рµ РєРЅРѕРїРєРё РїРѕРґ СЃРѕРѕР±С‰РµРЅРёСЏРјРё РґР»СЏ РЅР°РІРёРіР°С†РёРё.
Р’ Р»СЋР±РѕР№ РјРѕРјРµРЅС‚ РјРѕР¶РµС‚Рµ РІРµСЂРЅСѓС‚СЊСЃСЏ РІ РіР»Р°РІРЅРѕРµ РјРµРЅСЋ РєРѕРјР°РЅРґРѕР№ /menu

<b>РџРѕРґРґРµСЂР¶РєР°:</b>
РџРѕ РІСЃРµРј РІРѕРїСЂРѕСЃР°Рј РѕР±СЂР°С‰Р°Р№С‚РµСЃСЊ Рє Р°РґРјРёРЅРёСЃС‚СЂР°С‚РѕСЂСѓ.
    """
    
    await callback.message.edit_text(
        help_text,
        reply_markup=MenuKeyboards.back_button("main_menu")
    )
    await callback.answer()
