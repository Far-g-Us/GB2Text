---
name: Feature request [EN]
about: Suggest an idea for our project
title: "[Feature]"
labels: enhancement
assignees: Far-g-Us

---

### 🚀 Short description
Clearly name the new feature in one phrase

### 📖 Detailed description
Describe the functionality you want to see 

### 💡 Why is it important?
Explain the usefulness of the feature for the project
- [ ] Improves compatibility with games
- [ ] Simplifies the extraction process
- [ ] Adds a new type of analysis
- [ ] Solves problem #___

### ⚙️ Technical specification
**Expected behavior:**

[Specific technical description]

**Suggested implementation (if known):**
```python
# Pseudocode example
def new_feature(rom):
    if detect_game(rom) == "ZELDA":
        return extract_zelda_text(rom)
```

🔍 Alternatives
Have you considered other approaches?

🎮 Examples of use

# Example of a command with a new feature
gb2text extract --game="METROID2" --format=json

🌐 Additional context
-Related games: [Game name]
-Technical limitations: [Known issues]
-Analogues in other tools: [bgb, no$gmb, etc]

---

### 📂 How to add to the repository:
1. Create the file `.github/ISSUE_TEMPLATE/FEATURE_REQUEST.md`
2. Paste the contents above
3. Add to `README.md`:

## 🌟 Feature requests

Would you like to suggest an improvement?
1. Check [existing queries](https://github.com/Far-g-Us/gb2text/issues?q=is%3Aopen+is%3Aissue+label%3Aenhancement)
2. Create a new request using the [template](https://github.com/Far-g-Us/gb2text/issues/new?template=FEATURE_REQUEST.md)
