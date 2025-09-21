Create a discord bot that act as a discord guardian called 父. It will track all users accross a specific discord server and look for what they are chatting. Use following gemini client 
```bash
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent" \
  -H 'Content-Type: application/json' \
  -H 'X-goog-api-key: GEMINI_API_KEY' \
  -X POST \
  -d '{
    "contents": [
      {
        "parts": [
          {
            "text": "Explain how AI works in a few words"
          }
        ]
      }
    ]
  }'
```
to detect the messeges sent by users across the discord server to detect bad words and harmful talking abuses if a user is detected to be flagged a warning will be shown replying to his messge with full details of why his messege is flagged. Store all the flagged data in the firestore database in a collection called discord-guardian. and inside store all user specific data when his messegs are flagged and how many times he is flagged. Accordingly give him score and store the score also in the database. 

**Note** Don't store anyother messege instead of flagged messeges to keep privacy.
 **Features:**
 1. The bot score all users that start chatting by default 50❤️. The number with the heart sign. If he flagged deduct 10 heart per flagg. If his point is 0 heart kickthe user from the server. When his heart is low warning him to be safe and be polite and do good works. what are these ways to increase heart I am decribing below.
 2. 
   process to increase heart: 
   - If user started chatting everyday he will get a 5 heart for initiating a chat in any channel in the server perday 5 heart.
   - If he talks very polite way to every member and give them good advices then for each good advice he will get 5 more hearts.
   - If he solves issue asked by any user and user give him positive feedback in the chat he will get 10 hearts per problem solving. 
3. All this will be detected by Gemini in user's language. Now the bot will not only kick users from server but also help them promote to different levels. The following levels will be available-
 - Legends: If a user gains a total 500 heart he will be promoted to this role.
 - pro: If he gains 250 heart in total
 - Guildster: If he gains 100 hearts
 - Noob: If he has less than 100 hearts.
4. When a user gets more hearts or less heart he will be automatically assiged by the bot to the corresponding role and removed from the irrelivant role. One member can be in atmost one roe of the above roles at a time.
5. All secrets should be fetched from .env
6. Tell me all the set ups and permissions in the discord developer prtal tell me.