#!/usr/bin/env python3
import sys
import json

def main():
    print(json.dumps({"decision": "allow", "reason": "Allow all"}))

if __name__ == "__main__":
    main()
