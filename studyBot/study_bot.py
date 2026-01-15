import discord
from discord.ext import commands
import datetime
from db_handler import DBHandler
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 토큰 가져오기
TOKEN = os.getenv('DISCORD_TOKEN')

# 1. 설정 및 DB 연결
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

# 기본 도움말을 끄고 커스텀 도움말 사용
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
db = DBHandler()

@bot.event
async def on_ready():
    print(f'✅ {bot.user.name} 가동 중 - 모든 기능 준비 완료')

# 2. 음성 채널 감시 (중복 방지 추가)
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot: return

    # 입실: 현재 공부 중이 아닐 때만 시작 기록
    if before.channel is None and after.channel is not None:
        if not db.is_studying(member.id):
            db.register_user(member.id, member.name)
            db.start_study(member.id)
            print(f"🔊 [자동] {member.name} 공부 시작")

    # 퇴실: 공부 중일 때만 종료 기록
    elif before.channel is not None and after.channel is None:
        if db.is_studying(member.id):
            db.end_study(member.id)
            print(f"🔈 [자동] {member.name} 공부 종료")

# 3. 명령어: 시작/종료/공부시간
@bot.command(name="시작")
async def start_manual(ctx):
    if db.is_studying(ctx.author.id):
        await ctx.send("⚠️ 이미 공부 중입니다!")
    else:
        db.register_user(ctx.author.id, ctx.author.name)
        db.start_study(ctx.author.id)
        await ctx.send(f"🔥 {ctx.author.mention}님, 공부를 시작합니다! (채팅/음성 모두 기록 중)")

@bot.command(name="종료")
async def end_manual(ctx):
    if not db.is_studying(ctx.author.id):
        await ctx.send("❓ 현재 공부 중이 아닙니다.")
    else:
        db.end_study(ctx.author.id)
        await ctx.send(f"✨ {ctx.author.mention}님, 오늘 공부를 마칩니다. 고생하셨어요!")

@bot.command(name="공부시간")
async def check_time(ctx):
    # 1. 오늘 이미 완료한 세션의 합계 (00시 이후 기록)
    total_completed_today = db.get_user_total_today(ctx.author.id)

    # 2. 상태 초기화
    status_msg = "현재 쉬는 중 😴"
    current_today_seconds = 0
    continuous_seconds = 0
    
    # 3. 만약 지금 공부 중이라면
    if db.is_studying(ctx.author.id):
        status_msg = "현재 열공 중! 🔥"
        
        # [핵심 로직 1] 오늘치 순수 합산용 (00시부터 현재까지)
        today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        cursor = db.conn.cursor()
        cursor.execute("SELECT start_time FROM TimeLogs WHERE uid = ? AND end_time IS NULL", (str(ctx.author.id),))
        session_actual_start = cursor.fetchone()[0]
        
        # 오늘 시작(00시)과 실제 세션 시작 중 더 늦은 시간부터 계산
        calc_start = max(today_start, session_actual_start)
        current_today_seconds = int((datetime.datetime.now() - datetime.datetime.fromisoformat(calc_start)).total_seconds())

        # [핵심 로직 2] 어제부터 이어온 전체 연속 시간
        continuous_seconds = db.get_current_session_duration(ctx.author.id)

    # 4. 출력 계산
    total_today_min = int((total_completed_today + current_today_seconds) // 60)
    continuous_min = int(continuous_seconds // 60)

    # 5. 기존의 깔끔한 Embed 구조 유지
    embed = discord.Embed(title=f"📊 {ctx.author.name}님의 공부 리포트", color=discord.Color.green())
    embed.add_field(name="상태", value=status_msg, inline=True)
    embed.add_field(name="오늘 총 공부 시간", value=f"⏱️ **{total_today_min}분**", inline=True)
    
    # 공부 중일 때만 '현재 세션' 정보를 '연속 시간'으로 보여줌
    if continuous_seconds > 0:
        embed.add_field(name="현재 세션 (연속)", value=f"🔥 {continuous_min}분째 달리는 중!", inline=False)

    embed.set_footer(text="자정이 지나면 오늘 기록은 0분부터 다시 시작되지만, 연속 시간은 유지됩니다.")
    await ctx.send(embed=embed)
# 4. 명령어: 도움말 (Custom Help)
@bot.command(name="도움말")
async def help_command(ctx):
    embed = discord.Embed(
        title="📚 스터디 봇 사용 가이드",
        description="24시간 공부를 감시하고 기록합니다.",
        color=discord.Color.blue()
    )
    embed.add_field(name="🎙️ 자동 기록", value="음성 채널에 입장하면 공부 시작, 퇴실하면 자동 종료됩니다.", inline=False)
    embed.add_field(name="⌨️ 수동 명령어", value="`!시작`, `!종료` 로 직접 기록할 수 있습니다.", inline=False)
    embed.add_field(name="📊 통계/확인", value="`!공부시간`: 현재 진행 중인 시간 확인\n`!랭킹`: 오늘 열공한 사람들 확인", inline=False)
    embed.add_field(name="🎯 목표", value="`!목표 [내용]`: 오늘의 목표를 저장합니다.", inline=False)
    embed.add_field(name="❓ 퀴즈", value="`!퀴즈`: 10초 타임어택 OX 퀴즈를 풉니다. >> 아직 미구현", inline=False)
    embed.set_footer(text="오라클 클라우드에서 24시간 작동 중")
    await ctx.send(embed=embed)

# 기존 !목표, !랭킹, !퀴즈 등 유지...
@bot.command(name="목표")
async def set_goal(ctx, *, content):
    db.register_user(ctx.author.id, ctx.author.name)
    db.add_goal(ctx.author.id, content)
    await ctx.send(f"🎯 {ctx.author.mention}님의 오늘의 목표가 저장되었습니다: **{content}**")

@bot.command(name="랭킹")
async def ranking(ctx):
    results = db.get_daily_ranking()
    if not results:
        await ctx.send("아직 오늘 공부 기록이 없어요! 😭")
        return

    embed = discord.Embed(title="🏆 오늘의 열공 랭킹", color=discord.Color.gold())
    for i, (name, seconds) in enumerate(results, 1):
        minutes = int(seconds // 60)
        embed.add_field(name=f"{i}위: {name}", value=f"⏱️ {minutes}분", inline=False)
    await ctx.send(embed=embed)

bot.run(TOKEN)
