# PageRank Explorer: study data in Supabase

```
pagerank-study/
├── src/index.html     the lesson (no keys inside)
├── build.py           reads .env → writes dist/index.html
├── backup.py          downloads all four tables to backups/*.zip
├── .env.example       copy to .env and fill in
├── .gitignore         keeps .env, dist/ and backups/ out of git
```

Participants never see any timing or tracking. Python 3 is all you need; there's nothing to install.

## Setup

1. **Database.** In Supabase, open **SQL Editor**, click **+ New query**, paste all of `database.sql` and click **Run**. If Supabase warns about a destructive operation, click **Run this query**. That warning is about removing an earlier version; your data is kept, and you can run the file again at any time.
2. **Keys.** Copy `.env.example` to `.env` and fill it in from **Project Settings → API Keys**:

   | `.env` variable | Value | Used by |
   |---|---|---|
   | `SUPABASE_URL` | Project URL | the page and `backup.py` |
   | `SUPABASE_PUBLISHABLE_KEY` | publishable key (older projects: anon) | the page |
   | `SUPABASE_SECRET_KEY` | secret key (older projects: service_role) | `backup.py` only |

3. **Try it.** Run `python build.py --serve`, open http://localhost:8000, fill in the intake form and enter the lesson. A row appears in `participants`, `section_status` and `quiz_answers`.
4. **Put it online.** Either:
   - drag `dist/index.html` onto app.netlify.com/drop, or
   - connect the repository to Netlify and set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` under **Environment variables**.

## The four tables

All four are linked by `session_id`.

```
participants      1 row per participant
 ├── section_status   1 row per participant
 ├── quiz_answers     1 row per participant
 └── events           many rows per participant
```

All times are in Zurich time.

### `participants`

| Column | Example |
|---|---|
| session_id | key |
| name, email | from the intake form |
| age, gender, academic_level, consent | 20–25, Female, Master's, true |
| assigned_condition | ai / control (from the link `?condition=`), otherwise empty |
| learning_path | World Changer / Classic web. Empty until chosen |
| theme | Football, Music, Cooking, Food trip, Batman, Own topic, Classic web pages |
| story_source | prepared story / own topic / classic |
| world_input | what they typed or picked in the world picker |
| current_stage | Intake form, Lesson: Damping, Finished … |
| sections_completed | 0–6 |
| completed, completed_at | true/false, date and time |
| lesson_time_min | Final completed − Intro entered |
| times_left_page | switched to another tab, app or window and came back |
| page_reloads | |
| created_at, updated_at | started, last activity |
| token | technical: a random secret kept in the participant's browser tab, so only that tab can write to this row |
| state | technical: saved progress, so a reload or a return by email continues exactly where they were |

Rows with an empty `name` are visits that never submitted the intake form. Leave them out with `where name is not null`.

### `section_status`: one row per participant (6 lesson stages)

For each of `intro`, `surfer`, `probabilities`, `convergence`, `damping` and `final`:

| Column | Meaning |
|---|---|
| *stage*_entered_at | first time they opened the stage |
| *stage*_completed_at | when they moved on after passing its quiz (Final: lesson finished) |
| *stage*_time_sec | completed − entered, quiz included |
| *stage*_quiz_entered_at | quiz question first shown (not for Intro) |
| *stage*_quiz_completed_at | quiz answered correctly (Damping: its second question) |
| *stage*_quiz_time_sec | the quiz part on its own |

Reading time without the quiz is `_time_sec − _quiz_time_sec`.

### `quiz_answers`: one row per participant (6 questions)

| Question | q1 | q2 | q3 | q4 | q5 | q6 |
|---|---|---|---|---|---|---|
| In stage | Surfer | Probabilities | Convergence | Damping | Damping | Final |

For each question *N*:

| Column | Meaning |
|---|---|
| qN_answers | every answer in order: `C✗ → IDK → B✓` means first C (wrong), then "I don't know", then B (right) |
| qN_entered_at | question first shown |
| qN_completed_at | answered correctly |
| qN_time_sec | completed − entered |

### `events`

The raw log of every action, with time, stage and details. `section_status` and `quiz_answers` are calculated from it automatically after every save.

## How sessions work

- **One browser tab is one session.** A reload continues exactly where the participant was.
- **The next person on the same computer** opens the link in a new tab and gets a fresh session.
- **Accidentally closed the tab?** Open the link again, click "Already started? Continue where you left off" and enter the same email.
- **`?condition=ai` or `?condition=control`** in the link fixes the learning path.

## Backups

The free plan has no automatic backups. After each day of sessions, run:

```bash
python backup.py
```

This saves all four tables, as CSV and JSONL, to `backups/pagerank-backup-<date>.zip`.

## Analysis in Python

In Supabase, click **Connect** and copy the **Session pooler** connection string. Then:

```python
# pip install pandas sqlalchemy psycopg[binary]
import pandas as pd
from sqlalchemy import create_engine
eng = create_engine("postgresql+psycopg://postgres.abcd1234:YOUR-DB-PASSWORD@aws-0-eu-central-2.pooler.supabase.com:5432/postgres")

people   = pd.read_sql("select * from participants where name is not null", eng)
sections = pd.read_sql("select * from section_status", eng)
quizzes  = pd.read_sql("select * from quiz_answers", eng)
data = people.merge(sections, on="session_id").merge(quizzes, on="session_id")

data.groupby("learning_path")[["surfer_time_sec", "surfer_quiz_time_sec", "lesson_time_min"]].median()
```

## Good to know

- **Free projects pause after a week with no activity.** Your data is kept; click **Restore** in the dashboard.
- **Times are clock times.** A break in the middle of a stage counts towards that stage; `times_left_page` shows who took breaks.
