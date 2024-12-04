def findClosestPlayer(target, strings): # Finding similar names to player
	distances = [(s, levenshteinDistance(target, s)) for s in strings]
	closest_string, closest_distance = min(distances, key=lambda x: x[1])
	return closest_string, closest_distance


def levenshteinDistance(s1, s2): # Useful distance code I found
    if len(s1) < len(s2):
        return levenshteinDistance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def characterDifference(str1, str2): # Calculating character difference
    difference = sum(1 for i in range(min(len(str1), len(str2))) if str1[i] != str2[i])

    difference += abs(len(str1) - len(str2))

    return difference


def innocenceProb(innocent_count, guilty_count, alpha=1): # Calculating innocence probability
    innocent_count *= 7
    if guilty_count < 2 and innocent_count == 0:
        innocent_count += 1

    total_accusations = innocent_count + guilty_count + 2 * alpha
    probability_innocent = (innocent_count + alpha) / total_accusations
    probability_guilty = (guilty_count + alpha) / total_accusations

    return probability_innocent * 100, probability_guilty * 100


def loadingBar(status): # Making the loading bar
    filled_length = status * 3
    empty_length = 30 - filled_length

    bar = '█' * filled_length + '░' * empty_length
    return bar


def stringToNumbers(input_string): # Some usernames are weird so I convert them to numbers
    values = [str(ord(char)) for char in input_string]
    return '_'.join(map(str, values))
        

def numbersToString(player_key): # Converting numbers back to string
    values = player_key.split('_')
    return ''.join(chr(int(num)) for num in values)


def timestampToSnowflake(timestamp): # Converting epoch timestamp to Discord snowflake
    DISCORD_EPOCH = 1420070400000
    timestamp_ms = timestamp - DISCORD_EPOCH
    snowflake = (timestamp_ms << 22) | (0 << 17) | (0 << 12) | 0
    return snowflake
