from transformers import pipeline
import re
import asyncio
from libs.utilities import *



sentiment_pipeline = pipeline("sentiment-analysis", device=-1, model='distilbert/distilbert-base-uncased-finetuned-sst-2-english') # Downloading AI model


replacements = { # This will replace unclear text for the AI
    "=": "is", "!=": "is not", "≠": "is not", "->": "leads to", "<-": "comes from", "+": "and", "-": "minus",
    "@": "at", "&": "and", "#": "number", "$": "dollars", "%": "percent", "*": "star", "/": "or",
    ">": "greater than", "<": "less than", "u": "you", "ur": "your", "r": "are", "b4": "before", "w/": "with",
    "w/o": "without", "wrt": "with respect to", "fwd": "forward", "pls": "please", "plz": "please", "idk": "I don't know",
    "imo": "in my opinion", "thx": "thanks", "tx": "thank you", "lmk": "let me know", "btw": "by the way", "np": "no problem",
    "atm": "at the moment", "asap": "as soon as possible", "omg": "oh my god", "tbh": "to be honest", "afaik": "as far as I know",
    "gonna": "going to", "wanna": "want to", "gotta": "got to", "kinda": "kind of", "sorta": "sort of", "lemme": "let me",
    "gotcha": "I understand", "dunno": "don't know", "cuz": "because", "lol": "laughing out loud", ":)": "smiles", ":(": "sad",
    ":D": "laughs", ":/": "unsure", ";)": "wink", "<3": "love", "brb": "be right back", "gtg": "got to go", "cu": "see you",
    "ily": "I love you", "ic": "I see", "jk": "just kidding", "ttyl": "talk to you later", "tho": "though"
}

confessions = [
	"i have scammed", "i am a scammer", "i scammed someone", "i'm scamming people", "i did scam",
    "i committed a scam", "i got caught scamming", "i used to scam", "i have done scams", "i admit to scamming",
	"i tried to scam", "i am guilty of scamming", "i am involved in scams", "i scammed someone before", "i was a scammer",
	"i participated in scams", "i scam people", "i was part of a scam", "i did a scam", "i'm guilty of scams", "i am a scam artist",
	"i have been scamming", "i am involved in a scam", "i got someone scammed", "i helped with a scam", "i confess to scamming",
	"i organized a scam", "i just scammed someone", "i was running a scam", "i took part in a scam"
]



def replaceText(input_item):
    input_text = input_item['content']
    for key, value in replacements.items():
        input_item['content'] = input_text.replace(f' {key} ', f' {value} ')
    return input_item


def isAccusation(message, player_name): # Checking for suspicious patterns
    patterns = [
        rf"{player_name} .* scam",
        rf"{player_name} .* steal",
        rf"{player_name} .* cheat",
        rf"dont trust "
    ]
    return any(re.search(pattern, message, re.IGNORECASE) for pattern in patterns)


def isBlacklisted(accuser_dict, player, username): # Check if player is blacklisted
    if username in accuser_dict and len(accuser_dict[username]) > 7:
        return True
    return False


async def getScammer(players, cache, player_cache, batch_updates, username, accusers_cache): # Will determine if messages are accusations or not
    player_cache_keys = set(player_cache.keys())
    blacklist_compensation = 0
    accusations = []
    for player in players:
        if len(player) > 70: # If player has too many msgs it is considered spam
            continue

        player_key = stringToNumbers(player)

        msgs = players[player]
        msg_group = [replaceText({'content': msg['content'], 'id': msg['id']}) for msg in msgs]

        if player == username or characterDifference(username, player) < len(username) / 2: # Looking for any players with names too similar
            for msg in msg_group:
                if any(confession in msg['content'] for confession in confessions):
                    accusations.append({'player': player, 'conclusion': 'confession', 'msgs': msg_group})
                    break
            continue

        key_list = list(cache.keys())

        if player_key in player_cache_keys and 'innocence' in player_cache[player_key]: # Adjusting reliability coefficient based on their innocence probability
            innocence_value = player_cache[player_key]['innocence']
            if innocence_value >= 50:
                reliability_coefficient = 4
            else:
                reliability_coefficient = .3
        else:
            reliability_coefficient = 1

        amount_accusations = []
        skipped = 0
        judge_list = []
        find_cache = []
        guilty = False
        skip_player = False
        for msg in msg_group:
            content = msg['content']
            if '?' in content or f'[Reply to {username}]' in content and ' he ' in content and ' you' not in content: # Useless message, skipping
                skipped += 1
                if len(msg_group) == skipped: # Skip player if they're all useless
                    skip_player = True
            elif any(phrase in content.lower() for phrase in ([" isn't ", ' isnt ', ' no scam', ' is not '])): # No scam accusation, skipping
                continue
            elif isAccusation(content, username): # Looking for more patterns
                guilty = True
                amount_accusations.append(msg['id'])
            elif msg['id'] not in key_list:
                judge_list.append(msg)
            else:
                find_cache.append(msg)

        if len(judge_list) >= 1 and not guilty:
            response = await asyncio.to_thread(sentiment_pipeline, [msg['content'] for msg in judge_list]) # Using sentiment-analysis model
                    
            for index, msg in enumerate(response):
                msg_id = judge_list[index]['id']
                if msg['label'] == 'NEGATIVE' and msg['score'] > .9: # Negative is a scam accusation in this case
                    batch_updates[f'message_cache/{msg_id}/'] = msg
                    guilty = True
                    amount_accusations.append(msg_id)
                elif msg['label'] == 'POSITIVE' and msg['score'] > .9:
                    batch_updates[f'message_cache/{msg_id}/'] = msg
                else:
                    continue
        
        if len(find_cache) >= 1 and not guilty:
            response = [cache[msg['id']] for msg in find_cache]

            for index, msg in enumerate(response):
                if msg['label'] == 'NEGATIVE' and msg['score'] > .9:
                    guilty = True
                    amount_accusations.append(find_cache[index]['id'])
                elif msg['label'] == 'POSITIVE' and msg['score'] > .9:
                    continue
                else:
                    continue
        
        if not skip_player:
            if player_key in accusers_cache and isBlacklisted(accusers_cache[player_key], player, username): # Ignore if player is blacklisted for too many false accusations
                blacklist_compensation += 1
                continue

            if guilty:
                accusations.append({'player': player, 'conclusion': 'guilty', 'msgs': msg_group, 'rel': reliability_coefficient})
                batch_updates[f'accusers_cache/{player_key}/{username}/'] = amount_accusations
            else:
                accusations.append({'player': player, 'conclusion': 'innocent', 'msgs': msg_group, 'rel': reliability_coefficient})

    return accusations, cache, batch_updates, blacklist_compensation
