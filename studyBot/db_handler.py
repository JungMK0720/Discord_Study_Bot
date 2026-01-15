import sqlite3
from datetime import datetime

class DBHandler:
    def __init__(self, db_path="database.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # 1. Users Table
        cursor.execute('''CREATE TABLE IF NOT EXISTS Users (
                            uid TEXT PRIMARY KEY, uname TEXT)''')
        # 2. Goals Table (1:N)
        cursor.execute('''CREATE TABLE IF NOT EXISTS Goals (
                            gid INTEGER PRIMARY KEY AUTOINCREMENT,
                            uid TEXT, day TEXT, content TEXT,
                            is_completed INTEGER DEFAULT 0,
                            updated_at TEXT,
                            FOREIGN KEY (uid) REFERENCES Users(uid))''')
        # 3. TimeLogs Table (N:1)
        cursor.execute('''CREATE TABLE IF NOT EXISTS TimeLogs (
                            tid INTEGER PRIMARY KEY AUTOINCREMENT,
                            uid TEXT, start_time TEXT, end_time TEXT,
                            entry_type TEXT DEFAULT 'SYSTEM',
                            is_valid INTEGER DEFAULT 1,
                            FOREIGN KEY (uid) REFERENCES Users(uid))''')
        # 4. DailySummaries Table (Composite PK)
        cursor.execute('''CREATE TABLE IF NOT EXISTS DailySummaries (
                            uid TEXT, day TEXT, summary_content TEXT,
                            total_duration INTEGER DEFAULT 0,
                            PRIMARY KEY (uid, day),
                            FOREIGN KEY (uid) REFERENCES Users(uid))''')
        self.conn.commit()

    # --- 기능 함수 예시 ---
    def register_user(self, uid, uname):
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO Users VALUES (?, ?)", (uid, uname))
        self.conn.commit()

    def add_goal(self, uid, content):
        day = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO Goals (uid, day, content, updated_at) VALUES (?, ?, ?, ?)",
                       (uid, day, content, now))
        self.conn.commit()

    def start_study(self, uid):
        now = datetime.now().isoformat()
        with self.conn:
            # 시작 시간만 있고 종료 시간은 없는 행 추가
            self.conn.execute("INSERT INTO TimeLogs (uid, start_time, entry_type) VALUES (?, ?, 'SYSTEM')", 
                             (str(uid), now))

    def end_study(self, uid):
        now = datetime.now().isoformat()
        with self.conn:
            # 해당 유저의 가장 최근 NULL인 종료 시간을 업데이트
            self.conn.execute("""
                UPDATE TimeLogs SET end_time = ? 
                WHERE uid = ? AND end_time IS NULL 
                ORDER BY start_time DESC LIMIT 1
            """, (now, str(uid)))

    def get_daily_ranking(self):
        day = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.cursor()
        # 오늘 날짜의 세션별 (종료시간 - 시작시간) 합산 쿼리
        # SQLite의 strftime을 사용하여 초 단위 계산
        cursor.execute("""
            SELECT U.uname, SUM((strftime('%s', T.end_time) - strftime('%s', T.start_time))) as total
            FROM TimeLogs T
            JOIN Users U ON T.uid = U.uid
            WHERE T.end_time IS NOT NULL AND T.start_time LIKE ? AND T.is_valid = 1
            GROUP BY T.uid ORDER BY total DESC LIMIT 5
        """, (f"{day}%",))
        return cursor.fetchall()

    def is_studying(self, uid):
        """현재 공부 중(종료 시간이 없는 데이터 존재)인지 확인"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT tid FROM TimeLogs WHERE uid = ? AND end_time IS NULL", (str(uid),))
        return cursor.fetchone() is not None

    def get_current_session_duration(self, uid):
        """현재 진행 중인 세션의 경과 시간(초) 계산"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT strftime('%s', 'now', 'localtime') - strftime('%s', start_time)
            FROM TimeLogs WHERE uid = ? AND end_time IS NULL
        """, (str(uid),))
        row = cursor.fetchone()
        return row[0] if row else 0

# --- db_handler.py에 추가 ---

    def get_user_total_today(self, uid):
        """특정 유저의 오늘 총 공부 시간(초) 합산"""
        day = datetime.now().strftime('%Y-%m-%d')
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT SUM(strftime('%s', end_time) - strftime('%s', start_time))
            FROM TimeLogs
            WHERE uid = ? AND end_time IS NOT NULL AND start_time LIKE ? AND is_valid = 1
        """, (str(uid), f"{day}%"))
        row = cursor.fetchone()
        return row[0] if row[0] else 0

# --- db_handler.py에 추가 및 수정 ---

    def get_continuous_start_time(self, uid):
        """자정에 잘린 세션을 포함하여, 실제로 공부를 '처음 시작한' 시각을 찾아냄"""
        cursor = self.conn.cursor()
        current_start = None
        
        # 1. 현재 진행 중인 세션의 시작 시간 가져오기
        cursor.execute("SELECT start_time FROM TimeLogs WHERE uid = ? AND end_time IS NULL", (str(uid),))
        row = cursor.fetchone()
        if not row: return None
        current_start = row[0]

        # 2. 만약 시작 시간이 00:00:00이라면, 어제 23:59:59에 끝난 기록이 있는지 재귀적으로 탐색
        while current_start and "T00:00:00" in current_start:
            today_dt = datetime.strptime(current_start, "%Y-%m-%dT%H:%M:%S")
            yesterday_end = (today_dt - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")
            
            cursor.execute("SELECT start_time FROM TimeLogs WHERE uid = ? AND end_time = ?", (str(uid), yesterday_end))
            prev_row = cursor.fetchone()
            if prev_row:
                current_start = prev_row[0]
            else:
                break
        return current_start

    def get_current_session_duration(self, uid):
        """[수정] 실제 처음 시작한 시간부터 현재까지의 총 시간(초) 계산"""
        first_start = self.get_continuous_start_time(uid)
        if not first_start: return 0
        
        start_dt = datetime.strptime(first_start, "%Y-%m-%dT%H:%M:%S")
        now_dt = datetime.now()
        return int((now_dt - start_dt).total_seconds())
