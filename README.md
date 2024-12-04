# Shatty: Scam Scanner
Reading messages in Discord to determine if a Minecraft player is a scammer.

## Setup
This bot is originally made for EarthMc but can easily be changed by changing the guild_id.
If you want to make a bot with this code, don't forget to change all code mentioning Shatty.
Add your user_id to the ADMIN variable in main.py for admin permissions.

### Database
The bot uses firebase as database, create a firebase realtime database and add the database_url to .env,
then generate a service accounts key called credentials.json and add it to the main folder.
Firebase is completely free, the free plan does have limits but the bot won't use that much.

### Tokens
To be able to read Discord messages you need to find your user token and add it to the .env file.
Then create a bot and add the bot's token to the file too.

### Running the code
First install the libraries:
``pip install -r requirements.txt``
Then run the code, and wait for it to download the sentiment-analysis model.
