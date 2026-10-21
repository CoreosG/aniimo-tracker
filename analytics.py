"""Read-only chart data: loot is inventory value, wallet checkpoints are cash."""
from datetime import date, datetime, time, timedelta


def build_report(ledger, days=30, today=None):
    if days is not None and (type(days) is not int or days < 1):
        raise ValueError('Choose a positive day count or all time.')
    today = today or ledger.game_day()
    runs, spending = ledger.runs(), ledger.spending()
    purchases, rewards = ledger.purchases(), ledger.ticket_rewards()
    corrections = list(reversed(ledger.corrections()))
    settings = ledger.settings()
    activity = runs + spending + purchases + rewards
    checkpoint_days = [(datetime.fromisoformat(row['timestamp'])-timedelta(hours=settings['reset_hour'])).date()
                       for row in corrections]
    start = today - timedelta(days=days-1) if days else min(
        [date.fromisoformat(row['day']) for row in activity if row['day'] <= str(today)]+
        [day for day in checkpoint_days if day <= today] or [today])
    daily = {}
    for index in range((today-start).days+1):
        day = str(start+timedelta(days=index))
        daily[day] = dict(day=day,runs=0,failed=0,loot=0,known_loot=0,unknown_loot=0,
                          costs=0,gained=0,lost=0,bought=0,free=0,used=0)
    selected = []
    for run in runs:
        if run['day'] not in daily:
            continue
        selected.append(run)
        item = daily[run['day']]
        item['runs'] += 1
        item['failed'] += int(bool(run['failed']))
        item['gained'] += max(0,run['points'])
        item['lost'] += max(0,-run['points'])
        item['used'] += int(bool(run['consumes_ticket']))
        item['costs'] += run['expenses']
        if run['money'] is None:
            item['unknown_loot'] += 1
        else:
            item['known_loot'] += 1
            item['loot'] += run['money']
    for row in spending:
        if row['day'] in daily:
            daily[row['day']]['costs'] += row['amount']
    for row in purchases:
        if row['day'] in daily:
            daily[row['day']]['costs'] += row['cost']
            daily[row['day']]['bought'] += row['count']
    for row in rewards:
        if row['day'] in daily:
            daily[row['day']]['free'] += row['count']
    entries = list(daily.values())
    costs = sum(item['costs'] for item in entries)
    for item in entries:
        if item['unknown_loot'] and not item['known_loot']:
            item['loot'] = None
    samples = [row['points'] for row in selected if row['consumes_ticket'] and not row['failed']]
    state = ledger.summary()
    beginning = datetime.combine(start,time(hour=settings['reset_hour']))
    ending = datetime.combine(today+timedelta(days=1),time(hour=settings['reset_hour']))
    wallet = []
    predecessor = None
    for row in corrections:
        stamp = datetime.fromisoformat(row['timestamp'])
        point = dict(timestamp=row['timestamp'],coins=row['coins'],estimated=bool(row['estimated']),
                     approximate=bool(row['approximate']),reason=row['reason'],carried=False)
        if stamp < beginning:
            predecessor = point
        elif stamp < ending:
            wallet.append(point)
    if predecessor:
        wallet.insert(0,{**predecessor,'timestamp':beginning.isoformat(timespec='seconds'),'carried':True,
                         'reason':'Last saved balance before this range'})
    wallet_known = bool(corrections) or settings['starting_coins'] != 0
    if wallet_known and today == ledger.game_day():
        wallet.append(dict(timestamp=datetime.now().isoformat(timespec='seconds'),coins=state['coins'],
                           estimated=state['coins_estimated'],approximate=state['coins_approximate'],
                           reason='Current wallet estimate' if state['coins_estimated'] else 'Current recorded balance',carried=False))
    change = wallet[-1]['coins']-wallet[0]['coins'] if len(wallet)>1 else None
    return dict(start=str(start),end=str(today),daily=entries,current_wallet=state['coins'],
                wallet=wallet,wallet_change=change,wallet_known=wallet_known,
                wallet_estimated=state['coins_estimated'],wallet_approximate=state['coins_approximate'],
                totals=dict(runs=len(selected),failed=sum(bool(row['failed']) for row in selected),
                    loot=sum(row['money'] for row in selected if row['money'] is not None),
                    unknown_loot=sum(row['money'] is None for row in selected),costs=costs,
                    net_points=sum(row['points'] for row in selected),
                    average_points=sum(samples)/len(samples) if samples else None))
