Email summarizer hacked into [llama.cpp](https://github.com/ggerganov/llama.cpp). Extremely hacky. Probably someone somewhere has already done this with langchain, but man does langchain have a lot of confusing stuff piled up. This is a nice simple pair of C++ binaries with no special dependencies - just like the wonderful llama.cpp itself. Boy have things gotten interesting the past couple of months! I wonder what it'll look like in a year :O

The relevant files are:
* fetch_email_batch.py: Does the IMAP stuff, and does its best to yank plain text out of the email bodies. Writes those cleaned bodies into emails/.
* llama.cpp's examples/main, hacked up to just take in a prompt, do the LLM magic, and print to stdout.
* email_summary_getter.cpp: Calls fetch_email_batch.py, feeds the written email bodies into the modified `main`, writes the results into email_summaries/.

See https://developers.google.com/identity/protocols/oauth2 and/or https://github.com/google/gmail-oauth2-tools/blob/master/python/oauth2.py for how to get yourself an OAuth2 setup that Google will let you access your gmail inbox with. Then mkdir in here a directory called "sensitive" and fill in the files sensitive/emailaddr.txt, sensitive/client_secret.txt, sensitive/refreshtoken.txt, and sensitive/app_url.txt.

Once you have all that OAuth2 stuff set up, a simple `make && ./email_summary_getter` ought to write summaries of your last 5 days of email into email_summaries.

Oh you should also `mkdir emails email_summaries` in here. Finally, set up a gmail filter action thing to apply a
tag called "p" to all messages you want this setup to actually see. (Or change the argument to `imap_conn.select()` in fetch_email_batch.py to whatever label you want, or no label at all for everything.)

And the file ../LLModels/gpt4-x-alpaca-native-13B-ggml_q4_1.bin needs to exist relative to this directory.
