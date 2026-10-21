"""Run ledger and projections. All point entries are actual awarded points."""
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from contextlib import contextmanager
import math

DEFAULTS = dict(rank=177, rank_points=0, tickets=105, target=1000,
                deadline='2026-12-09', points_per_rank=180, daily_tickets=15,
                normal_points=190, first_points=320, reset_hour=0,
                monitor=0, capture_target='auto', starting_coins=0, lifetime_offset=None, prices=None, regions={},
                gear_price=120000, gear_discount_price=60000, gear_discount_count=3,
                gear_slots=2, gear_life=2, key_price=100000, solo_keys=2, party_keys=1,
                budget_party=False, play_days_week=7, runs_per_play_day=0,
                run_minutes=12, extra_minutes=0, screenshot_runs=30)
PRICES = [20000, 50000, 70000] + [100000] * 3 + [200000] * 4 + [300000] * 5 + [400000] * 5
EMPEROR_THRESHOLD = 14550


def _failed_result(points, failed):
    if type(points) is not int:
        raise ValueError('Point change must be a whole number, negative for a loss.')
    if type(failed) not in (bool, int) or failed not in (0, 1):
        raise ValueError('Failed run must be on or off.')
    if failed and points > 0:
        raise ValueError('A failed run must have zero or negative points.')
    return int(bool(failed or points < 0))


def ticket_cost(count, already_bought=0, prices=None):
    prices = PRICES if prices is None else prices
    if count < 0 or already_bought < 0 or count + already_bought > len(prices):
        raise ValueError('Daily purchases must fit the configured price table (20 by default).')
    return sum(prices[already_bought:already_bought + count])


def break_even(settings):
    """Weekly cash budget, including buy-only days and full replacement sets.

    This is a planning model, not a deduction from the observed wallet. A weekly
    budget rounds replacement sets up; unused durability is a small safety margin.
    """
    s={**DEFAULTS,**settings}
    daily=ticket_cost(s['daily_tickets'],prices=s['prices'])
    runs=(s['runs_per_play_day'] or s['daily_tickets'])*s['play_days_week']
    sets=math.ceil(runs/s['gear_life']) if runs else 0
    discounted=min(sets,s['gear_discount_count'])
    gear=s['gear_slots']*(discounted*s['gear_discount_price']+(sets-discounted)*s['gear_price'])
    keys=(s['party_keys'] if s['budget_party'] else s['solo_keys'])*s['key_price']
    total=daily*7+gear+keys*runs
    return dict(weekly_runs=runs,weekly_gear=gear,weekly_total=total,
                daily_tickets_cost=daily,keys_per_run=keys,
                tickets_per_run=daily*7/runs if runs else None,
                gear_per_run=gear/runs if runs else None,
                per_run=total/runs if runs else None,
                regular_gear_per_run=s['gear_slots']*s['gear_price']/s['gear_life'])


class Ledger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (
                  id INTEGER PRIMARY KEY, timestamp TEXT, day TEXT, points INTEGER,
                  money INTEGER, expenses INTEGER, bonus INTEGER, money_image TEXT,
                  points_image TEXT, notes TEXT, consumes_ticket INTEGER);
                CREATE TABLE IF NOT EXISTS purchases (
                  id INTEGER PRIMARY KEY, day TEXT, count INTEGER, cost INTEGER);
                CREATE TABLE IF NOT EXISTS ticket_rewards (
                  id INTEGER PRIMARY KEY, timestamp TEXT, day TEXT, count INTEGER, source TEXT);
                CREATE TABLE IF NOT EXISTS draft (id INTEGER PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS spending (
                  id INTEGER PRIMARY KEY, timestamp TEXT, day TEXT, amount INTEGER, note TEXT);
                CREATE TABLE IF NOT EXISTS corrections (
                  id INTEGER PRIMARY KEY, timestamp TEXT, rank INTEGER, rank_points INTEGER,
                  tickets INTEGER, coins INTEGER, run_cutoff INTEGER, purchase_cutoff INTEGER,
                  spending_cutoff INTEGER, reason TEXT, approximate INTEGER, estimated INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS run_starts (
                  id INTEGER PRIMARY KEY, timestamp TEXT, day TEXT, balance INTEGER,
                  screenshot TEXT, approximate INTEGER, run_id INTEGER, cancelled INTEGER DEFAULT 0);
            ''')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(runs)')}
            for name, definition in [('applied', 'INTEGER NOT NULL DEFAULT 1'),
                                     ('start_id', 'INTEGER'), ('source_key', 'TEXT'),
                                     ('failed', 'INTEGER NOT NULL DEFAULT 0')]:
                if name not in columns:
                    db.execute(f'ALTER TABLE runs ADD COLUMN {name} {definition}')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS run_source ON runs(source_key) WHERE source_key IS NOT NULL')
            if 'estimated' not in {row['name'] for row in db.execute('PRAGMA table_info(corrections)')}:
                db.execute('ALTER TABLE corrections ADD COLUMN estimated INTEGER DEFAULT 0')
            if 'reward_cutoff' not in {row['name'] for row in db.execute('PRAGMA table_info(corrections)')}:
                db.execute('ALTER TABLE corrections ADD COLUMN reward_cutoff INTEGER DEFAULT 0')
            if 'lifetime_points' not in {row['name'] for row in db.execute('PRAGMA table_info(corrections)')}:
                db.execute('ALTER TABLE corrections ADD COLUMN lifetime_points INTEGER')
                saved = db.execute('SELECT value FROM settings WHERE id=1').fetchone()
                previous = {**DEFAULTS, **(json.loads(saved[0]) if saved else {})}
                if previous['lifetime_offset'] is not None:
                    db.execute('UPDATE corrections SET lifetime_points=?+rank*?+rank_points',
                               (previous['lifetime_offset'], previous['points_per_rank']))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def settings(self):
        with self.connect() as db:
            row = db.execute('SELECT value FROM settings WHERE id=1').fetchone()
        return {**DEFAULTS, **(json.loads(row[0]) if row else {})}

    def configure(self, **changes):
        settings = {**self.settings(), **changes}
        if settings['lifetime_offset'] is not None and (type(settings['lifetime_offset']) is not int or settings['lifetime_offset']<0):
            raise ValueError('Egg Emperor threshold must be a non-negative whole number.')
        if type(settings['screenshot_runs']) is not int or settings['screenshot_runs']<0:
            raise ValueError('Screenshot retention must be a non-negative whole number.')
        for key in ('points_per_rank', 'normal_points', 'first_points'):
            if int(settings[key]) <= 0:
                raise ValueError(key + ' must be positive.')
        for key in ('rank', 'rank_points', 'tickets', 'target', 'daily_tickets', 'starting_coins'):
            if int(settings[key]) < 0:
                raise ValueError(key + ' cannot be negative.')
        if settings['rank_points'] >= settings['points_per_rank']:
            raise ValueError('Rank progress must be below points per rank.')
        if not 0 <= settings['reset_hour'] <= 23:
            raise ValueError('Reset hour must be between 0 and 23 in your PC timezone.')
        date.fromisoformat(settings['deadline'])
        prices = settings['prices'] if settings['prices'] is not None else PRICES
        if len(prices) != 20 or any(not isinstance(p, int) or p < 0 for p in prices):
            raise ValueError('Enter exactly 20 non-negative ticket prices.')
        if settings['daily_tickets'] > len(prices):
            raise ValueError('Daily ticket target cannot exceed the shop limit.')
        for key in ('gear_price','gear_discount_price','gear_discount_count','gear_slots','key_price','solo_keys','party_keys','runs_per_play_day'):
            if not isinstance(settings[key],int) or settings[key]<0:
                raise ValueError(key+' must be a non-negative whole number.')
        if not isinstance(settings['gear_life'],int) or settings['gear_life']<1:
            raise ValueError('Gear life must be at least one run.')
        if not 1<=settings['play_days_week']<=7:
            raise ValueError('Play days per week must be between 1 and 7.')
        if type(settings['run_minutes']) is not int or not 1 <= settings['run_minutes'] <= 15:
            raise ValueError('Minutes in each run must be a whole number from 1 to 15.')
        if type(settings['extra_minutes']) is not int or settings['extra_minutes'] < 0:
            raise ValueError('Extra minutes per run must be a non-negative whole number.')
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO settings VALUES(1,?)', (json.dumps(settings),))

    def game_day(self, now=None):
        return ((now or datetime.now()) - timedelta(hours=self.settings()['reset_hour'])).date()

    def runs(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM runs ORDER BY id DESC')]

    def record_run(self, *, points, money=None, expenses=0, bonus=False, day=None,
                   money_image='', points_image='', notes='', consumes_ticket=True,
                   applied=True, start_id=None, source_key=None, failed=False):
        failed = _failed_result(points, failed)
        if any(type(n) is not int or n < 0 for n in ((expenses,) if money is None else (money,expenses))):
            raise ValueError('Loot and expenses must be non-negative whole numbers.')
        day = str(day or self.game_day())
        date.fromisoformat(day)
        if applied and consumes_ticket and self.summary(date.fromisoformat(day))['tickets'] < 1:
            raise ValueError('No tickets left. Log a ticket purchase or correct starting tickets.')
        with self.connect() as db:
            if source_key:
                existing = db.execute('SELECT id FROM runs WHERE source_key=?', (source_key,)).fetchone()
                if existing:
                    return existing['id']
            if start_id is not None:
                start = db.execute('SELECT * FROM run_starts WHERE id=?', (start_id,)).fetchone()
                if not start or start['run_id'] is not None or start['cancelled']:
                    raise ValueError('This run start is no longer active.')
            cur = db.execute('''INSERT INTO runs(timestamp,day,points,money,expenses,bonus,
                money_image,points_image,notes,consumes_ticket,applied,start_id,source_key,failed)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (datetime.now().isoformat(timespec='seconds'), day, points, money, expenses,
                 int(bonus), money_image, points_image, notes, int(consumes_ticket),
                 int(applied), start_id, source_key, failed))
            if start_id is not None:
                db.execute('UPDATE run_starts SET run_id=? WHERE id=?', (cur.lastrowid, start_id))
            if applied:
                db.execute('DELETE FROM draft')
            return cur.lastrowid

    def update_run(self, run_id, **changes):
        """Correct one saved result in place; authoritative stat checkpoints still win."""
        editable = {'points', 'money', 'expenses', 'day', 'notes', 'consumes_ticket', 'applied', 'failed'}
        if changes.keys() - editable:
            raise ValueError('Only result values, date, notes and counting options can be edited.')
        with self.connect() as db:
            original = db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if original is None:
                raise ValueError('This saved run no longer exists.')
            row = {**dict(original), **changes}
            row['failed'] = _failed_result(row['points'], changes.get('failed',
                original['failed'] if row['points'] == 0 else False))
            for key in ('money', 'expenses'):
                if key == 'money' and row[key] is None:
                    continue
                if type(row[key]) is not int or row[key] < 0:
                    raise ValueError('Loot and expenses must be non-negative whole numbers.')
            date.fromisoformat(row['day'])
            if not isinstance(row['notes'], str):
                raise ValueError('Notes must be text.')
            for key in ('consumes_ticket', 'applied'):
                if type(row[key]) not in (bool, int) or row[key] not in (0, 1):
                    raise ValueError('Counting options must be on or off.')
                row[key] = int(row[key])
            checkpoint = db.execute('SELECT run_cutoff FROM corrections ORDER BY id DESC LIMIT 1').fetchone()
            after_checkpoint = run_id > (checkpoint['run_cutoff'] if checkpoint else 0)
            old_use = int(bool(original['applied'] and original['consumes_ticket'] and after_checkpoint))
            new_use = int(bool(row['applied'] and row['consumes_ticket'] and after_checkpoint))
            if new_use > old_use and self.summary()['tickets'] < new_use - old_use:
                raise ValueError('No tickets left. Log a ticket purchase or correct current tickets.')
            db.execute('''UPDATE runs SET points=?,money=?,expenses=?,day=?,notes=?,consumes_ticket=?,applied=?,failed=?
                          WHERE id=?''', tuple(row[key] for key in
                          ('points', 'money', 'expenses', 'day', 'notes', 'consumes_ticket', 'applied', 'failed')) + (run_id,))

    def delete_run(self, run_id):
        with self.connect() as db:
            db.execute('UPDATE run_starts SET cancelled=1 WHERE run_id=?', (run_id,))
            db.execute('DELETE FROM runs WHERE id=?', (run_id,))

    def correct_stats(self, *, rank=None, rank_points=None, tickets=None, coins=None,
                      lifetime_points=None, reason='Manual correction', approximate=None):
        state, settings = self.summary(), self.settings()
        rank_entered = rank is not None or rank_points is not None
        threshold = state['emperor_threshold']
        if lifetime_points is not None:
            if type(lifetime_points) is not int or lifetime_points < 0:
                raise ValueError('Lifetime points must be a non-negative whole number.')
            if not rank_entered:
                rank, rank_points = divmod(max(0, lifetime_points-threshold), settings['points_per_rank'])
        values = dict(rank=state['rank'] if rank is None else rank,
                      rank_points=state['rank_points'] if rank_points is None else rank_points,
                      tickets=state['tickets'] if tickets is None else tickets,
                      coins=state['coins'] if coins is None else coins)
        for key, value in values.items():
            if not isinstance(value, int) or (key != 'coins' and value < 0):
                raise ValueError('Stats must be whole numbers; rank and tickets cannot be negative.')
        if values['rank_points'] >= settings['points_per_rank']:
            raise ValueError('Progress must be below points per rank.')
        if lifetime_points is not None and rank_entered:
            settings['lifetime_offset'] = lifetime_points - values['rank'] * settings['points_per_rank'] - values['rank_points']
            if settings['lifetime_offset']<0:
                raise ValueError('Total points cannot be below the entered Egg Emperor progress.')
        elif lifetime_points is None:
            lifetime_points = (threshold + values['rank'] * settings['points_per_rank'] + values['rank_points']
                               if rank_entered and state['lifetime_points'] is not None else state['lifetime_points'])
        with self.connect() as db:
            if lifetime_points is not None and rank_entered:
                db.execute('INSERT OR REPLACE INTO settings VALUES(1,?)', (json.dumps(settings),))
            cutoffs = [db.execute(f'SELECT COALESCE(MAX(id),0) FROM {table}').fetchone()[0]
                       for table in ('runs','purchases','spending')]
            reward_cutoff=db.execute('SELECT COALESCE(MAX(id),0) FROM ticket_rewards').fetchone()[0]
            return db.execute('''INSERT INTO corrections(timestamp,rank,rank_points,tickets,coins,
                run_cutoff,purchase_cutoff,spending_cutoff,reason,approximate,estimated,reward_cutoff,lifetime_points)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (datetime.now().isoformat(timespec='seconds'), values['rank'], values['rank_points'],
                 values['tickets'], values['coins'], *cutoffs, reason,
                 int(state['coins_approximate'] if approximate is None else approximate),
                 int(state['coins_estimated'] if coins is None else False),reward_cutoff,lifetime_points)).lastrowid

    def corrections(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM corrections ORDER BY id DESC')]

    def update_balance_checkpoint(self,checkpoint_id,coins,approximate=False):
        """Edit the original wallet observation; preserve stat cutoffs and runs."""
        if type(coins) is not int or coins<0:raise ValueError('Balance must be a non-negative whole number.')
        with self.connect() as db:
            row=db.execute('SELECT * FROM corrections WHERE id=?',(checkpoint_id,)).fetchone()
            if row is None:raise ValueError('Balance checkpoint no longer exists.')
            db.execute('UPDATE corrections SET coins=?,approximate=? WHERE id=?',(coins,int(bool(approximate)),checkpoint_id))

    def active_start(self):
        with self.connect() as db:
            row = db.execute('SELECT * FROM run_starts WHERE run_id IS NULL AND cancelled=0 ORDER BY id DESC LIMIT 1').fetchone()
        return dict(row) if row else None

    def starts(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM run_starts ORDER BY id DESC')]

    def start_run(self, balance=None, screenshot='', approximate=False):
        if balance is not None and (not isinstance(balance, int) or balance < 0):
            raise ValueError('Balance must be a non-negative whole number.')
        if self.active_start():
            raise ValueError('A run is already active. Save its results or cancel it before starting another.')
        if balance is not None:
            self.correct_stats(coins=balance, reason='Inventory balance at run start', approximate=approximate)
        with self.connect() as db:
            return db.execute('INSERT INTO run_starts(timestamp,day,balance,screenshot,approximate) VALUES(?,?,?,?,?)',
                (datetime.now().isoformat(timespec='seconds'), str(self.game_day()), balance,
                 screenshot, int(approximate))).lastrowid

    def cancel_start(self):
        with self.connect() as db:
            db.execute('UPDATE run_starts SET cancelled=1 WHERE run_id IS NULL AND cancelled=0')

    def buy(self, count, day=None):
        if not isinstance(count, int) or count < 1:
            raise ValueError('Buy at least one ticket.')
        day = str(day or self.game_day())
        with self.connect() as db:
            bought = db.execute('SELECT COALESCE(SUM(count),0) FROM purchases WHERE day=?', (day,)).fetchone()[0]
            cost = ticket_cost(count, bought, self.settings()['prices'])
            db.execute('INSERT INTO purchases VALUES(NULL,?,?,?)', (day, count, cost))
        return cost

    def award_tickets(self,count,source='Chest reward',day=None):
        if type(count) is not int or count<1:
            raise ValueError('Enter a positive whole number of free tickets.')
        day=str(day or self.game_day());date.fromisoformat(day)
        with self.connect() as db:
            return db.execute('INSERT INTO ticket_rewards(timestamp,day,count,source) VALUES(?,?,?,?)',
                (datetime.now().isoformat(timespec='seconds'),day,count,source.strip() or 'Chest reward')).lastrowid

    def purchases(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM purchases ORDER BY id DESC')]

    def ticket_rewards(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM ticket_rewards ORDER BY id DESC')]

    def spend(self, amount, note='', day=None):
        if not isinstance(amount, int) or amount <= 0:
            raise ValueError('Spending must be a positive whole number.')
        day = str(day or self.game_day())
        date.fromisoformat(day)
        with self.connect() as db:
            return db.execute('INSERT INTO spending VALUES(NULL,?,?,?,?)',
                (datetime.now().isoformat(timespec='seconds'), day, amount, note)).lastrowid

    def spending(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM spending ORDER BY id DESC')]

    def delete_spending(self, expense_id):
        with self.connect() as db:
            db.execute('DELETE FROM spending WHERE id=?', (expense_id,))

    def save_draft(self, value):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO draft VALUES(1,?)', (json.dumps(value),))

    def draft(self):
        with self.connect() as db:
            row = db.execute('SELECT value FROM draft WHERE id=1').fetchone()
        return json.loads(row[0]) if row else {}

    def summary(self, today=None):
        today = today or self.game_day()
        s = self.settings()
        runs = self.runs()
        spending = self.spending()
        rewards=self.ticket_rewards()
        with self.connect() as db:
            purchases = [dict(row) for row in db.execute('SELECT * FROM purchases')]
            checkpoint = db.execute('SELECT * FROM corrections ORDER BY id DESC LIMIT 1').fetchone()
        cp = dict(checkpoint) if checkpoint else dict(rank=s['rank'], rank_points=s['rank_points'],
            tickets=s['tickets'], coins=s['starting_coins'], run_cutoff=0, purchase_cutoff=0,
            spending_cutoff=0, approximate=0, estimated=0,reward_cutoff=0,lifetime_points=None)
        new_runs = [r for r in runs if r['applied'] and r['id'] > cp['run_cutoff']]
        new_purchases = [p for p in purchases if p['id'] > cp['purchase_cutoff']]
        new_spending = [e for e in spending if e['id'] > cp['spending_cutoff']]
        earned = sum(r['points'] for r in new_runs)
        total_points = cp['rank'] * s['points_per_rank'] + cp['rank_points'] + earned
        threshold = s['lifetime_offset'] if s['lifetime_offset'] is not None else EMPEROR_THRESHOLD
        lifetime_points = cp['lifetime_points']
        if lifetime_points is None and s['lifetime_offset'] is not None:
            lifetime_points=cp['rank']*s['points_per_rank']+cp['rank_points']+s['lifetime_offset']
        if lifetime_points is not None:
            lifetime_points=max(0,lifetime_points)
            # runs() is newest first. A loss at zero cannot consume points from
            # a later successful award; each recorded result has its own floor.
            for run in reversed(new_runs):lifetime_points=max(0,lifetime_points+run['points'])
        emperor_points = max(0, lifetime_points-threshold) if lifetime_points is not None else total_points
        rank, rank_points = divmod(emperor_points, s['points_per_rank'])
        tickets = cp['tickets'] + sum(p['count'] for p in new_purchases) - sum(r['consumes_ticket'] for r in new_runs) + sum(r['count'] for r in rewards if r['id']>cp['reward_cutoff'])
        unknown_loot=sum(r['money'] is None for r in runs)
        net = None if unknown_loot else sum(r['money'] - r['expenses'] for r in runs) - sum(e['amount'] for e in spending)
        bought_today = sum(p['count'] for p in purchases if p['day'] == str(today))
        today_runs = [r for r in runs if r['day'] == str(today)]
        normal_samples = [r['points'] for r in runs if r['consumes_ticket'] and not r['failed']]
        normal = sum(normal_samples) / len(normal_samples) if normal_samples else s['normal_points']
        # Failed outcomes affect rank/tickets, but do not train successful-run pace.
        return dict(rank=rank, rank_points=rank_points, tickets=tickets,
                    eggs=rank,is_emperor=lifetime_points>=threshold if lifetime_points is not None else None,
                    emperor_threshold=threshold,total_points=lifetime_points,
                    remaining=max(0, threshold+s['target']*s['points_per_rank']-lifetime_points)
                              if lifetime_points is not None else max(0,s['target']*s['points_per_rank']-total_points),
                    run_net=net, loot_value=sum(r['money'] for r in runs if r['money'] is not None),loot_unknown_runs=unknown_loot,
                    coins=cp['coins'] - sum(r['expenses'] for r in new_runs)
                          - sum(e['amount'] for e in new_spending) - sum(p['cost'] for p in new_purchases),
                    coins_approximate=bool(cp['approximate']),
                    coins_estimated=bool(cp['estimated'] or new_spending or new_purchases or any(r['expenses'] for r in new_runs)),
                    lifetime_points=lifetime_points,
                    bought_today=bought_today, today_runs=len(today_runs),
                    today_points=sum(r['points'] for r in today_runs),
                    today_net=-sum(r['expenses'] for r in today_runs)
                              - sum(e['amount'] for e in spending if e['day'] == str(today))
                              - sum(p['cost'] for p in purchases if p['day'] == str(today)),
                    normal=normal, bonus_used=any(r['bonus'] for r in today_runs))


def forecast(ledger, today=None):
    today = today or ledger.game_day()
    s, state = ledger.settings(), ledger.summary(today)
    days = max(0, (date.fromisoformat(s['deadline']) - today).days + 1)
    normal = state['normal']
    # Actual awards already include bonuses. Never add another bonus to that average.
    has_samples = any(r['consumes_ticket'] and not r['failed'] for r in ledger.runs())
    first = normal if has_samples else s['first_points']
    extra = max(0, first - normal)
    bonus_days = max(0, days - int(state['bonus_used']))
    lo, hi = 0, math.ceil(state['remaining'] / normal) if normal > 0 else 0
    while lo < hi:
        mid = (lo + hi) // 2
        if mid * normal + min(mid, bonus_days) * extra >= state['remaining']:
            hi = mid
        else:
            lo = mid + 1
    points, available, finish = 0, state['tickets'], today if not state['remaining'] else None
    for i in range(days):
        bought = max(0, s['daily_tickets'] - state['bought_today']) if i == 0 else s['daily_tickets']
        available += bought
        runs = available if i == 0 else bought
        gain = runs * normal + (extra if runs and (i > 0 or not state['bonus_used']) else 0)
        points += gain
        if finish is None and points >= state['remaining']:
            finish = today + timedelta(days=i)
    needed = lo if lo * normal + min(lo, bonus_days) * extra >= state['remaining'] else None
    play_minutes = None if needed is None else needed * s['run_minutes']
    session_minutes = None if needed is None else needed * (s['run_minutes'] + s['extra_minutes'])
    return dict(days=days, points=round(points), available_tickets=available,
                needed_tickets=needed, reachable=state['remaining'] == 0 or (days > 0 and points >= state['remaining']),
                finish=finish, margin=available - needed if needed is not None else None,
                daily_runs=math.ceil(needed / days) if days and needed is not None else 0,
                play_minutes=play_minutes,
                full_run_minutes=None if needed is None else needed * 15,
                daily_play_minutes=play_minutes / days if days and play_minutes is not None else None,
                session_minutes=session_minutes,
                daily_session_minutes=session_minutes / days if days and session_minutes is not None else None,
                daily_cost=ticket_cost(s['daily_tickets'], prices=s['prices']))
