#include <memory>
#include <string>
#include <cassert>
#include <filesystem>
#include <iostream>
#include <fstream>

using namespace std;

// Basically like VAR=`cmd` in bash.
string runShellSync(const char* cmd)
{
  char buffer[1024];
  string ret;
  unique_ptr<FILE, decltype(&pclose)> pipe(popen(cmd, "r"), pclose);
  assert(pipe);

  while (fgets(buffer, 1024, pipe.get()) != nullptr)
    ret += buffer;
  return ret;
}

int main()
{
    runShellSync("rm emails/* ; rm email_summaries/* ; python3 fetch_email_batch.py");

    for (auto& entry : std::filesystem::directory_iterator("emails"))
    {
        string email_body_fnameonly = entry.path();
        email_body_fnameonly = email_body_fnameonly.substr(7);

        string email_body_fname = "emails/";
        email_body_fname += email_body_fnameonly;
        cerr << "opening: " << email_body_fname << endl;
        ifstream body_in(email_body_fname);
        if (!body_in)
        {
            cerr << "ERROR!!!! ERROR OPENING " << email_body_fname << endl;
            return 1;
        }
        string the_email_body;
        string line;
        while (getline(body_in, line))
            the_email_body += line + "\n";
        body_in.close();

        // truncate to at most 4000 characters
        if (the_email_body.length() > 4000)
            the_email_body = the_email_body.substr(0, 4000);

        cerr << "truncated body:\n" << the_email_body << endl;

        string summary_request =
            "Below is an instruction that describes a task. Write a response that appropriately completes the request.\n"
            "Summarize in one sentence the following email:\n"+
            the_email_body+"\nThe one sentence summary is:";
        ofstream tmpfile_out("/tmp/llamiku_email_summary_request.txt");
        tmpfile_out << summary_request;
        tmpfile_out.close();

        string summary = runShellSync("./main -m ../LLModels/gpt4-x-alpaca-native-13B-ggml_q4_1.bin  -c 2048 --temp 0.4 --top_k 40 --top_p 0.5 --repeat_last_n 500 --repeat_penalty 1.2 -t 4 -n 4096 --instruct --file /tmp/llamiku_email_summary_request.txt");
        if (summary.length() < 3)
            summary = "(failed to generate a summary for this email)";

        // I left printing of the original input prompt in llama_email_summarizer/main, so quick hack: find the actual output.
        auto start_ind = summary.find("The one sentence summary is:");
        if (start_ind != string::npos)
            summary = summary.substr(start_ind + 28); // strlen(The one sentence summary is:)


        string summary_out_path = "email_summaries/";
        summary_out_path += email_body_fnameonly;
        ofstream out(summary_out_path);
        cerr << "about to write to " << summary_out_path << " this summary: " << summary << endl;
        out << summary;
        out.close();
    }
}
