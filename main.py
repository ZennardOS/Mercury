import discord
import os
import asyncio
import yt_dlp
import requests
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from googlesearch import search
from deepseek import chat_stream  

def run():
    load_dotenv()
    TOKEN = 'YOUR_TOKEN_FROM_DISCORD_SERVICE'  # Replace with your token
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    voice_clients = {}
    queues = {}
    yt_dl_options = {"format": "bestaudio/best", "noplaylist": True}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn -filter:a "volume=0.25"'
    }

    @client.event
    async def on_ready():
        print(f'{client.user} working')

    @client.event
    async def on_message(message):
        if message.author == client.user:
            return

        # Обработка команды *deep
        if message.content.startswith("*deep"):
            try:
                print()
                query = message.content[len("*deep "):]
                if query:
                    await message.channel.send("Mercury is processing your request...")
                    response = await chat_stream(query)
                    
                    max_length = 1950
                    response_parts = []
                    current_part = ""

                    for line in response.splitlines():  
                        if len(current_part) + len(line) + 1 <= max_length:  
                            current_part += line + "\n"
                        else:
                            response_parts.append(current_part.strip())  
                            current_part = line + "\n"  

                    
                    if current_part.strip():
                        response_parts.append(current_part.strip())

                    
                    for i, part in enumerate(response_parts):
                        if i == 0:
                            await message.channel.send(f"\u200B\nHere's what Mercury managed to find:\n\n {part}")
                        else:
                            await message.channel.send(f"{part}")
                    print()
                    print("----------------------------------------------------------------------------------")
                    print()
                    print()
                else:
                    await message.channel.send("Please specify the query after the command *deep.")
            except Exception as ex:
                print(f"Mercury was unable to process your request: {ex}")
                await message.channel.send("An error occurred while processing your request Mercury.")

        
        if message.content.startswith("*play"):
            try:
                if not message.author.voice:
                    await message.channel.send("You must be in a voice channel to use this command.")
                    return

                if message.guild.id not in voice_clients or not voice_clients[message.guild.id].is_connected():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[message.guild.id] = voice_client
                    queues[message.guild.id] = []

                url = message.content.split()[1]

                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))

                song = data['url']
                title = data.get('title', 'No title found')
                queues[message.guild.id].append((song, title))

                if not voice_clients[message.guild.id].is_playing():
                    await play_next(message.guild.id, message.channel)
                else:
                    await message.channel.send(f"Added to queue: {title}")
            except Exception as ex:
                print(f"Error playing track: {ex}")
                await message.channel.send("An error occurred while playing the track.")

        if message.content.startswith("*turn"):
            try:
                if not message.author.voice:
                    await message.channel.send("You must be in a voice channel to use this command.")
                    return

                if message.guild.id not in voice_clients or not voice_clients[message.guild.id].is_connected():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[message.guild.id] = voice_client
                    queues[message.guild.id] = []

                query = message.content[len("*turn "):]
                if not query:
                    await message.channel.send("Please provide the title of the song.")
                    return

                search_query = f"ytsearch:{query}"
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(None, lambda: ytdl.extract_info(search_query, download=False))

                if 'entries' in data and data['entries']:
                    song = data['entries'][0]['url']
                    title = data['entries'][0].get('title', 'No title found')
                    queues[message.guild.id].append((song, title))

                    if not voice_clients[message.guild.id].is_playing():
                        await play_next(message.guild.id, message.channel)
                    else:
                        await message.channel.send(f"Added to queue: {title}")
                else:
                    await message.channel.send("Nothing found.")
            except Exception as ex:
                print(f"Error searching or playing track: {ex}")
                await message.channel.send("An error occurred while searching or playing the track..")

        if message.content.startswith("*pause"):
            try:
                voice_clients[message.guild.id].pause()
            except Exception as ex:
                print(f"Pause error: {ex}")

        if message.content.startswith("*resume"):
            try:
                voice_clients[message.guild.id].resume()
            except Exception as ex:
                print(f"Error when resuming: {ex}")

        if message.content.startswith("*stop"):
            try:
                voice_clients[message.guild.id].stop()
                await voice_clients[message.guild.id].disconnect()
                del voice_clients[message.guild.id]
                queues[message.guild.id] = []
            except Exception as ex:
                print(f"Error while pausing: {ex}")

        if message.content.startswith("*next"):
            try:
                voice_clients[message.guild.id].stop()
                await play_next(message.guild.id, message.channel)
            except Exception as ex:
                print(f"Error when switching tracks: {ex}")

        if message.content.startswith("*write"):
            try:
                query = message.content[len("*write "):]
                if query:
                    results = list(search(query, num_results=1))
                    if results:
                        await message.channel.send(results[0])
                    else:
                        await message.channel.send("No results found.")
                else:
                    await message.channel.send("Please provide a search query.")
            except Exception as ex:
                print(f"Error while searching: {ex}")
                await message.channel.send("An error occurred while searching.")

        if message.content.startswith("*perp"):
            query = message.content[len("*perp "):]
            response = get_perplexity_response(query)
            await message.channel.send(response)

    async def play_next(guild_id, channel):
        if queues[guild_id]:
            song, title = queues[guild_id].pop(0)
            player = discord.FFmpegOpusAudio(song, **ffmpeg_options)
            voice_clients[guild_id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(guild_id, channel), client.loop))
            await channel.send(f"Currently playing: {title}")

    def get_perplexity_response(query):
        query = query.replace(" ", "+")
        url = f"https://www.perplexity.ai/search?q={query}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            result_element = soup.find('div', class_='result')

            if result_element:
                answer = result_element.get_text(strip=True)
                return answer
            else:
                return "No results found"

        except Exception as ex:
            return f"Link from Mercury - https://www.perplexity.ai/search?q={query}"

    client.run(TOKEN)

run()