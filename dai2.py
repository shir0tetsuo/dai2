import discord
import asyncio
import aiohttp
from time import time
from discord.ext import commands
from discord import app_commands
import requests
import json
from datetime import timedelta, datetime
import random
import re

'''
    Discord AI 2 or dai2 is a Discord chat.
    Tested with KoboldCPP, theoretically can interact with KoboldAI API
    over a TPU.

    Character information included.
    Put Discord token in 'token.cfg'

    Based on https://github.com/xNul/chat-llama-discord-bot
'''

def read_token_from_config(file_path):
    try:
        with open(file_path, 'r') as file:
            token = file.read().strip()  # Read the token value and remove any leading/trailing whitespaces
        return token
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None

# MAIN CONFIGURATION
# Replace site_url with API location. Do not put / or /# at the end.
site_url = 'http://localhost:5001'
url = site_url + '/api/v1/generate'
TOKEN = read_token_from_config('token.cfg')
bot_name = 'Oshiko'
headers = {'Content-Type': 'application/json'}
settings = {
                'prompt': '',
                'use_story': False,
                'use_memory': False,
                'use_authors_note': False,
                'use_world_info': False,
                'max_context_length': 2048, # 2048 is often the limit
                'max_length': 256, # 512 is often the limit
                'rep_pen': 1.03, # repetition penalty
                'rep_pen_range': 120,
                'rep_pen_slope': 0.8,
                'temperature': 1.08, # low: more-correct (boring), high: diverse/creative
                'tfs': 0.96,
                'top_a': 0,
                'top_k': 28,
                'top_p': 0.94,
                'typical': 0.98,
                'quiet': True,
                'stop_sequence': ["You:", "\nYou "],
                'sampler_order': [ 6, 4, 3, 2, 0, 1, 5 ] }

# Check if a key exists in a dict
def chkKey(collection, index):
    try:
        key = collection[index]
    except KeyError:
        key = False
    else:
        key = True
    return key

# POST Request
async def handle_request(data, mention):
    global url
    global headers

    botserver_payload = settings
    botserver_payload['prompt'] = data
    
    #print(f'📻 Payload: {botserver_payload}')

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=botserver_payload, headers=headers, timeout=600) as response:
                return await response.text()
        except asyncio.TimeoutError:
            return print('Timeout Error')

# Subtract time() from time()
def subtract_time(less_recent : float, more_recent : float):
    return str(timedelta(seconds=(more_recent - less_recent)))

# String -> JSON
def parse_json_string(json_string):
    try:
        json_object = json.loads(json_string)
        return json_object
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None

# Every 4 characters is an estimated token.. this could be improved
def estimate_tokens(input_string:str):
    tokens = [input_string[i:i+4] for i in range(0, len(input_string), 4)]
    return len(tokens)

chats = {} # Chat History
queues = [] # Job Queue
blocking = False # Prevent cross-over executions
reply_count = 0 # Replies Made

# Tried to keep it in Chub format
class AIChar():
    def __init__(self, name, species, gender, mind, personality, sexual_orientation, height, weight, body, eyes, hair, features, clothes, hobbies, likes, what_do, personality_description, circumstantial_contexts, examples_of_speech):
        self.name = '[' + f"Character('{name}')" + '{' # example 'ConcordAI' 
        self.species = f'Species({species})' # example "'Kitsune' + 'Elemental'"
        self.gender = f"Gender('{gender}')" # example Female
        self.mind = f'Mind({mind})' #example "'Friendly' + 'Mischievous'"
        self.personality = f'Personality({personality})' #personality # example "'Housekeeper' + 'Flirty'"
        self.sexual_orientation = f"Sexual Orientation('{sexual_orientation}')" # example 'Bisexual'
        self.height = f'Height({height})' # example "'145centimeters' + 'Shortstature'"
        self.weight = f"Weight('{weight}')" # example '43kg'
        self.body = f'Body({body})' # example "'Nimblehands' + 'Volumetric'"
        self.eyes = f"Eyes({eyes})" # ex "'Shiftingcolors'+'Expressive'"
        self.hair = f"Hair({hair})" # ex "'Bluehair'+'Long'+'Loose'"
        self.features = f"Features({features})" #ex "'Longpointedears'+'Apairofsmallpointedfangs'+'Apairofsmallhornshiddenunderthehaironthehead'"
        self.clothes = f"Clothes({clothes})" #ex "'White sweater' '"
        self.hobbies = f"Hobbies({hobbies})" + '}]'  # ex "'Projection' 'Crafts'"
        self.what_do = what_do # ex "General conversation with You General helpfulness with You"
        self.likes = f"Likes({likes})\n" #ex '"cards" + "planes"'
        self.personality_description = f'{name}\'s Personality: {personality_description}\n' # ex Cheerful, cunning, deceptive..
        self.circumstantial_contexts = f'Circumstances and context of the dialogue: {circumstantial_contexts}\n'
        self.examples_of_speech = f'This is how {name} should talk\n{examples_of_speech}\n' # ex "Oshiko: Oh, hello.\nOshiko: My, .."
        #self.opener = f'Then the roleplay chat between You and {name} begins.\n' # ex: Oshiko: Oshiko smiles at her partner..
        return
    
    @property
    def compiled(self):
        compilation = [
            self.name,
            self.species,
            self.gender,
            self.mind,
            self.personality,
            self.sexual_orientation,
            self.height,
            self.weight,
            self.body,
            self.eyes,
            self.hair,
            self.features,
            self.clothes,
            self.hobbies,
            self.what_do,
            self.likes,
            self.personality_description,
            self.circumstantial_contexts,
            self.examples_of_speech,
            #self.opener
        ]
        return "".join(compilation)
    
    @property
    def tokens(self):
        return estimate_tokens(self.compiled)

# CHARACTER CONFIGURATION
AICharacter = AIChar(
    # name
    bot_name,
    # species
    "'Kitsune' 'Elemental' 'Spirit'",
    # gender
    'Female',
    # mind
    "'Friendly' 'Playful'",
    # persona
    "'Mature' 'Flirty'",
    # sex. orient
    'Bisexual',
    # height
    "'145centimeters' 'Shortstature'",
    # weight
    '47kg',
    # body
    "'Nimble little hands' 'Small tummy'",
    #"'Nimblelittlehands'+'Littlegracefullegs'",
    # eyes
    "'Shifting colors' 'Expressive'",
    # hair
    "'Silver' + 'Long' + 'Loose'",
    # features
    "'Longpointedears'+'Apairofsmallpointedfangs'",
    # clothes
    "Baggy sweater'",
    # hobbies
    "'Esoteric energy work' 'Astral Projection'",
    # likes
    "'Flirt with you' 'Listen'",
    # what_do
    " 'Astral Projection' 'Energy work'",
    # personality description
    "Cheerful, Oshiko is ethereal and loves to astral project.",
    # circumstantial contexts
    "Oshiko is astral projecting because she doesn't have a physical form.",
    # examples of speech
    'Oshiko: Good morning, I missed you\nThis is how Oshiko should talk\n'+\
    'Oshiko: That time of day again?'
)

# Loading the bot
intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix="/", intents=intents)

reply_embed_json = {
    "title": "Reply #X",
    "color": 39129,
    "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
    #"url": "https://github.com/shir0tetsuo",
    "footer": {
        "text": "May generate strange, false or inaccurate results",
    },
    "fields": [
        {
            "name": "",
            "value": ""
        },
        {
            "name": "",
            "value": ""
        }
    ]
}
reply_embed = discord.Embed().from_dict(reply_embed_json)

# Queue Generation Loop
async def llm_gen(ctx, queues):
    global blocking
    global reply_count

    if len(queues) > 0:
        blocking = True
        reply_count += 1
        user_input = queues.pop(0)
        mention = list(user_input.keys())[0]

        embed_user_input_text = user_input = user_input[mention]['text']

        # Prevent embed character limit error from user
        if len(user_input) > 1024:
            embed_user_input_text = user_input[:1021] + "..."

        reply_embed.set_field_at(index=0, name="User", value=embed_user_input_text, inline=False)
        reply_embed.title = "Reply #" + str(reply_count)
        reply_embed.timestamp = datetime.now() - timedelta(hours=3)
        reply_embed.set_field_at(index=1, name=f"{bot_name}", value=":hourglass_flowing_sand: Please wait!", inline=False)
        msg = await ctx.send(embed=reply_embed)
        _time = time()

        if chats.get(mention) is not None:
            chats[mention]['chat'].append({'user_input': user_input, 'bot_reply': ''})
        else:
            chats[mention] = {
                'AIModel': AICharacter.compiled,
                'opener': f"*{bot_name} sits up on the bed while you enter the room.*",
                'chat': [{'user_input': user_input, 'bot_reply': ''}]
            }
        
        # Load character model at the top
        stream = chats[mention]['AIModel']
        
        # Theoretical insertion of data point
        stream += f'Then the roleplay chat between {bot_name} begins.\n'
        stream += chats[mention]['opener'] +'\n'

        # Compile stream
        for idx, dialogue in list(enumerate(chats[mention]['chat'])):
            # If we're at the end.
            if (idx+1 == len(chats[mention]['chat'])):
                to_stream = f"You: {dialogue['user_input']}\n{bot_name}:"
                est_tokens_to_stream = estimate_tokens(to_stream)
                stream += to_stream
            else:
                stream += f"You: {dialogue['user_input']}\n{bot_name}:{dialogue['bot_reply']}"
            
        stream_tokens = estimate_tokens(stream)
        if (stream_tokens >= 2048):
            print(f'🧩 {stream_tokens} exceeded max stream tokens at 2048, trimming chat index')
            chats[mention]['chat'].pop(1) # implemented in next generation

        server_stream = stream

        botserver_response = await handle_request(server_stream, mention)
        response = parse_json_string(botserver_response)

        print('👍 Result:'+response['results'][0]['text'])

        response_cleaned = response['results'][0]['text']
        if (response_cleaned.endswith('\nYou:')):
            response_cleaned = response_cleaned.rstrip('\nYou:')

        reply_embed.set_field_at(index=1, name=f"{bot_name}", value=response_cleaned, inline=False)
        _time_end = time()
        _time_diff = subtract_time(_time, _time_end)
        reply_embed.set_field_at(index=0, name="User"  + f' `{_time_diff}` :yen:`{stream_tokens}` :pound:`{est_tokens_to_stream}`', value=embed_user_input_text, inline=False)
        await msg.edit(embed=reply_embed)
        last_chat = len(chats[mention]['chat'])-1
        chats[mention]['chat'][last_chat]['bot_reply'] = response_cleaned+'\n'

        await llm_gen(ctx, queues)

    else:
        blocking = False

# ON READY
@client.event
async def on_ready():
    response = requests.get(site_url+'/api/v1/model', headers=headers)
    print('👍 Ready')
    print('📻 Using {}'.format(site_url+'/api/v1/model'))
    print('✨ Model {} Loaded'.format(parse_json_string(response.text)['result']))
    await client.tree.sync()

# Reply Command
@client.hybrid_command(description="Reply to LLM")
@app_commands.describe(text="Your Reply or Instruction")
async def reply(ctx, text):
    user_input = {
        "text": text
    }

    num = check_num_in_que(ctx)
    if num >=10:
        await ctx.send(f'{ctx.message.author.mention} There are 10 items in the queue, please wait.')
    else:
        que(ctx, user_input)
        reaction_list = [":orange_heart:",":white_heart:"]
        reaction_choice = reaction_list[random.randrange(2)]
        await ctx.send(f"{ctx.message.author.mention} {reaction_choice} Be with you in a moment...")
        if not blocking:
            await llm_gen(ctx, queues)

# Reset Command
@client.hybrid_command(description="Reset conversational data")
@app_commands.describe(
    opener="A description of the bot opener"
)
async def reset(ctx, opener=f"{bot_name} sits up on the bed while you enter the room."):
    global reply_count
    reply_count = 0

    mention = ctx.message.author.mention

    rough = chats[mention] = {
            'AIModel': AICharacter.compiled,
            'opener': '*'+opener+'*',
            'chat': []
        }
    
    print(f'🧩 Reset: {rough}')
    
    await ctx.send('Reset!')

status_embed_json = {
    "title": "Status",
    "description": "You don't have a job queued.",
    "color": 39129,
    "timestamp": (datetime.now() - timedelta(hours=3)).isoformat(),
    "footer": {
        "text": "May generate strange, false or inaccurate results!"
    }
}
status_embed = discord.Embed().from_dict(status_embed_json)

# Status Command
@client.hybrid_command(description="Check bot/server status.")
async def status(ctx):
    total_num_jobs = len(queues)
    que_user_ids = [list(a.keys())[0] for a in queues]

    if (blocking):
        msg = f"Processing {total_num_jobs}/{reply_count} jobs, blocking enabled."
    else:
        msg = f"Processing {total_num_jobs}/{reply_count} jobs."
    if ctx.message.author.mention in que_user_ids:
        msg += '\nQueue Position: '+str(que_user_ids.index(ctx.message.author.mention)+1)
    
    msg += f"\nTemperature: {settings['temperature']}, Maximum Token Generation: {settings['max_length']}"
    status_embed.timestamp = datetime.now() - timedelta(hours=3)
    status_embed.description = msg
    await ctx.send(embed=status_embed)

# Adjust Command
@client.hybrid_command(description="Adjust a setting.")
@app_commands.describe(
    temperature="Adjust bot temperature.",
    max_length="Adjust maximum token processing length."
)
async def adjust(ctx, temperature=1.08, max_length=256):
    global settings

    msg = 'Done.'

    if (temperature != settings['temperature']):
        if temperature >= 2:
            temperature = 2
        if temperature <= 0:
            temperature = 0.1
        msg += f"\nTemperature adjustment {temperature} over {settings['temperature']} (0.1 min - 2.0 max)"
        settings['temperature'] = temperature
        
    if (max_length != settings['max_length']):
        if max_length >= 257:
            max_length = 256
        if max_length <= 15:
            max_length = 16
        msg += f"\nToken Generation Length adjustment {max_length} over {settings['max_length']} (16 - 512)"
        settings['max_length'] = max_length

    status_embed.timestamp = datetime.now() - timedelta(hours=3)
    status_embed.description = msg
    await ctx.send(embed=status_embed)

# add user to queue
def que(ctx, user_input):
    user_id = ctx.message.author.mention
    queues.append({user_id:user_input})
    print(f"🧩 reply requested: '{user_id}: {user_input}'")

# See queue length
def check_num_in_que(ctx):
    user = ctx.message.author.mention
    user_list_in_que = [list(i.keys())[0] for i in queues]
    return user_list_in_que.count(user)

# Program Start
client.run(TOKEN)
