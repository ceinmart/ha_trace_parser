#!/usr/bin/env python3
"""
Specialized Parser for Home Assistant Traces - v6.0
"""

# Required libraries:
#   - pyyaml
#   - tzlocal
#   - pytz
#   - colorama (optional, for colored CLI output)
#   - rich (optional, for pretty printing)
#
# Install all required libraries with:
#   pip install pyyaml tzlocal pytz
#
# For optional features:
#   pip install colorama rich
#
# ------------------------------------------------------

import json
import yaml
import pytz
from datetime import datetime
from pathlib import Path
import pprint
import tzlocal

# Settings
def get_timezone(cli_timezone=None):
    if cli_timezone:
        return cli_timezone
    try:
        return str(tzlocal.get_localzone())
    except Exception:
        return 'UTC'

def load_automation(yaml_file):
    """Loads the automation YAML and maps all paths with their aliases recursively, including aliases at any level and in any block.
    Also associates the alias with the item's path and main sub-blocks (if, then, else, repeat, choose, etc). Now, every level is mapped, even without an alias, using the inherited alias + relative path as the default value."""
    def map_steps(base, steps, mapping, nearest_alias=None, nearest_alias_path=None):
        if isinstance(steps, list):
            for idx, step in enumerate(steps):
                path = f"{base}/{idx}" if base else f"sequence/{idx}"
                local_alias = step.get('alias') if isinstance(step, dict) else None
                if local_alias:
                    mapping[path] = local_alias
                    inherited_alias = local_alias
                    inherited_alias_path = path
                else:
                    if nearest_alias:
                        # path_sublevel = path without the prefix of the inherited alias path
                        path_sublevel = path[len(nearest_alias_path):].lstrip('/') if nearest_alias_path else path
                        mapping[path] = f"{nearest_alias}//{path_sublevel}"
                    else:
                        mapping[path] = path
                    inherited_alias = nearest_alias
                    inherited_alias_path = nearest_alias_path
                if isinstance(step, dict):
                    for key, value in step.items():
                        map_steps(f"{path}/{key}", value, mapping, inherited_alias, inherited_alias_path)
        elif isinstance(steps, dict):
            local_alias = steps.get('alias')
            if local_alias and base:
                mapping[base] = local_alias
                inherited_alias = local_alias
                inherited_alias_path = base
            else:
                if nearest_alias and base:
                    path_sublevel = base[len(nearest_alias_path):].lstrip('/') if nearest_alias_path else base
                    mapping[base] = f"{nearest_alias}//{path_sublevel}"
                elif base:
                    mapping[base] = base
                inherited_alias = nearest_alias
                inherited_alias_path = nearest_alias_path
            for key, value in steps.items():
                map_steps(f"{base}/{key}" if base else key, value, mapping, inherited_alias, inherited_alias_path)
        # If not dict or list, do nothing

    with open(yaml_file, encoding='utf-8') as f:
        automation = yaml.safe_load(f)

    mapping = {}
    for key, value in automation.items():
        if key == 'sequence' or isinstance(value, (list, dict)):
            map_steps(key, value, mapping)
    return mapping

def process_trace(trace_file, alias_mapping, output_file=None, timezone=None):
    """Processes the trace file and structures the data. If output_file is provided, saves the result to the file."""
    tz = pytz.timezone(timezone) if timezone else pytz.timezone('UTC')
    event_list = []
    current_iteration = 0

    with open(trace_file) as f:
        trace_data = json.load(f)

    # Collect all events in a single list
    for event in trace_data['trace']['trace'].values():
        if isinstance(event, list):
            events = event
        else:
            events = [event]
        for ev in events:
            if not isinstance(ev, dict) or 'path' not in ev:
                continue
            event_list.append(ev)

    # Sort all events by timestamp (considering milliseconds)
    event_list.sort(key=lambda ev: datetime.fromisoformat(ev.get('timestamp')).timestamp() if 'timestamp' in ev else 0)

    output = []
    for ev in event_list:
        timestamp = datetime.fromisoformat(ev['timestamp']).astimezone(tz)
        path = ev['path']
        result = ev.get('result', {})
        error = ev.get('error')

        # Map correct alias (show friendly alias, not path)
        alias = alias_mapping.get(path)
        if not alias:
            # Try plural/singular variations for action(s), condition(s), trigger(s)
            variations = [
                path.replace('action/', 'actions/'),
                path.replace('actions/', 'action/'),
                path.replace('condition/', 'conditions/'),
                path.replace('conditions/', 'condition/'),
                path.replace('trigger/', 'triggers/'),
                path.replace('triggers/', 'trigger/'),
            ]
            for var in variations:
                if var in alias_mapping:
                    alias = alias_mapping[var]
                    break
        if not alias:
            alias = path

        # Detect new loop iterations
        if 'repeat' in path:
            current_iteration += 1
            output.append(f"\n[ITERATION {current_iteration}]")

        # Build log line
        line = {
            'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S.%f %Z'),
            'alias': alias,
            'path': path,
            'data': {}
        }

        # Add changed states (show all changed_variables content)
        if 'changed_variables' in ev:
            line['data']['changed_variables'] = ev['changed_variables']

        # Add result if exists
        if result:
            line['data']['result'] = result

        # Add errors
        if error:
            line['error'] = error

        output.append(line)
    # If output_file is provided, save the formatted output to the file (append mode to not overwrite)
    if output_file:
        formatted_output = format_output(output)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write("\n".join(formatted_output))
        return output  # still returns for compatibility
    return output

def format_output(processed_data):
    """Formats the output for friendly display"""
    output = []
    for entry in processed_data:
        if isinstance(entry, str):
            output.append(entry)
            continue
        # Show timestamp, alias and path
        line = f"{entry['timestamp']} | {entry['alias']} | {entry['path']}"
        if 'data' in entry:
            details = []
            for key, value in entry['data'].items():
                if isinstance(value, dict):
                    details.append(f"{key}: {json.dumps(value, indent=2, ensure_ascii=False)}")
                else:
                    details.append(f"{key}: {value}")
            if details:
                line += "\n  " + "\n  ".join(details)
        if 'error' in entry:
            line += f"\n  [ERROR] {entry['error']}"
        output.append(line)
    return output

def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('yaml_file')
    parser.add_argument('trace_log')
    parser.add_argument('-o', '--output', default=None, help='Output file (if omitted, print to screen)')
    parser.add_argument('-tz', '--timezone', default=None, help='Timezone to use for output (default: local timezone)')
    
    args = parser.parse_args()

    # File configuration
    yaml_file = args.yaml_file  # Your automation YAML file
    trace_file = args.trace_log  # Your Home Assistant trace file
    output_file = args.output
    timezone = get_timezone(args.timezone)
    
    # Load and display mapping
    mapping = load_automation(yaml_file)

    # Display full loaded YAML structure
    with open(yaml_file, encoding='utf-8') as f:
        automation_yaml = yaml.safe_load(f)

    # Validation: compare main alias from YAML with friendly_name from trace
    import json
    with open(trace_file, encoding='utf-8') as f:
        trace_data = json.load(f)
    # Try to find friendly_name in the first trigger/0 event
    friendly_name = None
    try:
        trigger0 = trace_data['trace']['trace']['trigger/0'][0]
        friendly_name = trigger0['changed_variables']['this']['attributes']['friendly_name']
    except Exception:
        pass
    main_alias = automation_yaml.get('alias')
    alert_name = ''
    if not friendly_name or not main_alias or friendly_name != main_alias:
        alert_name = f"[ALERT] The main alias from YAML ('{main_alias}') is different from the friendly_name in the trace ('{friendly_name}'). Make sure the trace matches the provided YAML.\n"

    yaml_structure = pprint.pformat(automation_yaml, sort_dicts=False, width=120)
    mapping_structure = pprint.pformat(mapping, sort_dicts=False, width=120)

    # Prepare execution parameters summary
    params_summary = (
        f"[PARAMETERS] yaml_file={yaml_file} | trace_log={trace_file} | output={output_file if output_file else '[stdout]'} | timezone={timezone}\n"
    )

    output_structure = (
        params_summary +
        alert_name +
        "\n[LOADED YAML - FULL STRUCTURE]\n" + yaml_structure +
        "\n\n[IDENTIFIED ALIAS MAPPING]\n" + mapping_structure
    )

    if not output_file:
        try:
            from colorama import Fore, Style, init as colorama_init
            from rich import print as rich_print
            colorama_init()
            use_rich = True
        except ImportError:
            use_rich = False
        if use_rich:
            # Use rich for pretty printing the YAML and mapping
            rich_print(f"[bold cyan]{params_summary}[/bold cyan]")
            if alert_name:
                rich_print(f"[bold red]{alert_name}[/bold red]")
            rich_print(f"[bold yellow][LOADED YAML - FULL STRUCTURE][/bold yellow]")
            rich_print(automation_yaml)
            rich_print(f"\n[bold yellow][IDENTIFIED ALIAS MAPPING][/bold yellow]")
            rich_print(mapping)
        else:
            print(params_summary)
            if alert_name:
                print(Fore.RED + alert_name + Style.RESET_ALL)
            print("[LOADED YAML - FULL STRUCTURE]")
            print(yaml_structure)
            print("\n[IDENTIFIED ALIAS MAPPING]")
            print(mapping_structure)
    else:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output_structure + "\n\n")
        print("\n[YAML and mapping loaded. Output will be saved to file, not displayed on screen.]")

    # Processing
    data = process_trace(trace_file, mapping, output_file if output_file else None, timezone)
    # If no output_file, print to screen (compatible mode)
    if not output_file:
        formatted_output = format_output(data)
        try:
            from colorama import Fore, Style, init as colorama_init
            colorama_init()
            for line in formatted_output:
                if '[ERROR]' in line:
                    print(Fore.RED + line + Style.RESET_ALL)
                elif '[ITERATION' in line:
                    print(Fore.CYAN + line + Style.RESET_ALL)
                else:
                    print(line)
        except ImportError:
            print("\n".join(formatted_output))

if __name__ == "__main__":
    main()
