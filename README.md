# ha_trace_parser

Hi, 

Tired of struggling with very confusing traces from my scripts and automation, I tried to create a Python code (using IA on VS Code + Copilot) to parse the YAML + trace file and produce a better and more understandable output. 

For now, appears to work. 
I'm not python developer, so , just give a shot with IA.  
I think that still a lot of situations to be treat, but for now, I they appear to be doing a good job.  
The initial objective with this code was: 

1. Reorder all steps in the timeline of the events and not groupped by each sequence. 
2. Adjust the timezone to you local timezone
3. link the path of each step with the alias on yaml code and show at the output. 

I'm running this code on my windows, where I install Python from microsot store, install the libraries using pip (see the comments on the code) , downloaded the trace file from H.A. interface  , saved manually the yaml of my script/automation.  
Then just run the command , something like this : C:\tmp\ha\trace_parser.py script.yaml trace.log.json -o relatorio_final.txt  
```
PS C:\tmp\ha> python3.13.exe C:\tmp\ha\trace_parser.py                                                                                         
usage: trace_parser.py [-h] [-o OUTPUT] [-tz TIMEZONE] yaml_file trace_log                                                                     
trace_parser.py: error: the following arguments are required: yaml_file, trace_log
```
