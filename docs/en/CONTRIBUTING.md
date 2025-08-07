# How to contribute to GB Text Extraction Framework

Thank you for wanting to contribute to GB Text Extraction Framework! This document explains how you can help in the development of the project, observing the legal restrictions.

## ⚠️ Important legal warning

**Please review our before making a contribution [LICENSE](../../LICENSE.md)**.

This project:
- DOES NOT contain or distribute any ROM files of commercial games
- It is intended ONLY for use with home (homebrew) ROM files created by you yourself
- Should NOT be used to analyze commercial games without the explicit permission of the copyright holder

**Violation of these rules will result in rejection of your contribution and possible removal from the project.**

## How to contribute safely

### 1. Configuration files (`plugins/config/`)

- **IT IS ACCEPTABLE** to add configurations ONLY for:
  - Home (homebrew) games created by you
  - Examples unrelated to real commercial games

- **IT is UNACCEPTABLE** to add configurations for:
  - Commercial games (Pokémon, Zelda, etc.)
  - ROM files not created by you yourself
  
- **Example of a secure configuration**:
```json
{
"game_id_pattern": "^HOME_BREW_[A-Z0-9]+_[0-9A-F]{2}$",
"segments": [
  {
    "game_id_pattern": "^HOME_BREW_[A-Z0-9]+_[0-9A-F]{2}$",
    "segments": [
      {
        "name": "main_text",
        "start": "0x4000",
        "end": "0x5000",
        "charmap": {
          "0x20": " ",
          "0x41": "A",
          "0x42": "B",
          "0xFF": "[END]"
        }
      }
    ]
  }
```

### 2. Character tables and encodings 

- **IT IS ACCEPTABLE** to add:
  - Basic ASCII characters (A-Z, a-z, 0-9, punctuation)
  - General Japanese characters without reference to specific games
         

- **IT IS NOT ALLOWED** to add: 
  - Game-specific elements (for example, "PK", "MN", "POKéMON")
  - Exact symbol tables that match the structure of commercial games
  - Elements that can be regarded as trademarks
         
     

### 3. Guides (guides/) 

- **IT IS ACCEPTABLE** to create guides for:
  - Home games created by you
  - General principles of working with the framework
         

- **IT IS UNACCEPTABLE** to create guides for:
  - Specific commercial games
  - Instructions on how to work with illegal copies of games
         
     

### The process of making changes 

#### 1. Create an issue before starting work on a new feature or fix 
- Discuss whether your idea meets the legal requirements of the project.
- Make sure that your idea does not infringe on copyrights

#### 2. Create a branch for your work: 


`git checkout -b feature/your-feature-name`


#### 3. Follow the code standards: 
- Add a legal warning to the beginning of each file.
- Avoid mentioning commercial games in the code
- Write clear comments
         

#### 4. Create a Pull Request with a description of the changes: 
- Explain clearly how your contribution meets the legal requirements.
- Specify which games (if any) are supported by your contribution
- Confirm that you are following all the rules in this document.

### An example of a secure deposit 

A good example of a contribution: 

- Adding support for a new type of compression (without being tied to specific games)
- Improvement of the automatic character table detection algorithm
- Creating a template for home games


A bad example of a contribution: 

- Adding a plugin for Pokémon with a specific symbol table
- Enabling text segment addresses for Zelda
- Creating a guide for working with illegal ROMs


### Mandatory confirmation 

Before your contribution is accepted, you must confirm the following:

    "I confirm that my contribution is:"
    1. It does not contain information specific to commercial games
    2. It is intended ONLY for use with home (homebrew) ROM files
    3. Does not infringe on the copyrights of third parties
    4. Meets all the requirements set out in the LICENSE and this document

### Thanks for understanding! 

Your compliance with these rules helps keep the project safe and accessible to legitimate users. Together, we can create a powerful tool for research purposes without violating copyrights. 

Nintendo, Pokémon, The Legend of Zelda, and all related trademarks are the property of their respective owners.