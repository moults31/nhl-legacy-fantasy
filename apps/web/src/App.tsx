import { useEffect, useMemo, useState } from "react";
import "./App.css";

interface Team {
  slug: string;
  city: string;
  full_name: string;
  abbrev: string;
}

interface Player {
  id: string;
  first_name: string;
  last_name: string;
  main_team_slug: string | null;
}

interface SeasonTeam {
  record: number;
  city: string;
  abbrev: string | null;
  full_name: string | null;
}

interface SeasonPlayer {
  record: number;
  first_name: string;
  last_name: string;
  proteam: number;
}

interface SeasonEvent {
  id: number;
  day: number;
  text_key: string;
}

interface SeasonGmState {
  record: number;
  gm_first_name: string;
  gm_last_name: string;
  current_day: number;
}

interface SeasonScheduleEntry {
  id: number;
  game_index: number;
  day: number;
  home_team: number | null;
  away_team: number | null;
  home_goals: number;
  away_goals: number;
  val1: number;
  val2: number;
  event_type: number;
  event_flag: number;
  is_future: boolean;
}

interface SeasonPerformanceEntry {
  record: number;
  gm_first_name: string;
  gm_last_name: string;
  current_day: number;
  budget_score: number;
  performance_score: number;
  active: number;
  team_index: number;
}

interface SeasonTransactionEntry {
  id: number;
  record: number;
  day: number;
  event_index: number;
  sub_type: number;
  player_name: string | null;
  team_name: string | null;
  with_team_name: string | null;
}

const API_BASE = "/api";

function App() {
  const [tab, setTab] = useState<"roster" | "season">("roster");
  const [teams, setTeams] = useState<Team[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  // Season state
  const [seasonDay, setSeasonDay] = useState<number>(0);
  const [seasonTeams, setSeasonTeams] = useState<SeasonTeam[]>([]);
  const [seasonPlayers, setSeasonPlayers] = useState<SeasonPlayer[]>([]);
  const [seasonEvents, setSeasonEvents] = useState<SeasonEvent[]>([]);
  const [seasonGmStates, setSeasonGmStates] = useState<SeasonGmState[]>([]);
  const [selectedSeasonTeam, setSelectedSeasonTeam] = useState<number | null>(null);
  const [seasonSchedule, setSeasonSchedule] = useState<SeasonScheduleEntry[]>([]);
  const [seasonPerformance, setSeasonPerformance] = useState<SeasonPerformanceEntry[]>([]);
  const [seasonTxns, setSeasonTxns] = useState<SeasonTransactionEntry[]>([]);
  const [userTeamIndices, setUserTeamIndices] = useState<number[]>([]);
  const [tweetLabels, setTweetLabels] = useState<Record<string, string>>({});

  useEffect(() => {
    fetch(`${API_BASE}/teams`)
      .then((r) => r.json())
      .then(setTeams)
      .catch(() => setStatus("Failed to load teams"));
    fetch(`${API_BASE}/players`)
      .then((r) => r.json())
      .then(setPlayers)
      .catch(() => setStatus("Failed to load players"));
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/season/state`)
      .then((r) => r.json())
      .then((s) => setSeasonDay(s.current_day))
      .catch(() => {});
    fetch(`${API_BASE}/season/teams`)
      .then((r) => r.json())
      .then(setSeasonTeams)
      .catch(() => {});
    fetch(`${API_BASE}/season/players`)
      .then((r) => r.json())
      .then(setSeasonPlayers)
      .catch(() => {});
    fetch(`${API_BASE}/season/events`)
      .then((r) => r.json())
      .then(setSeasonEvents)
      .catch(() => {});
    fetch(`${API_BASE}/season/gm-states`)
      .then((r) => r.json())
      .then(setSeasonGmStates)
      .catch(() => {});
    fetch(`${API_BASE}/season/schedule`)
      .then((r) => r.json())
      .then(setSeasonSchedule)
      .catch(() => {});
    fetch(`${API_BASE}/season/performance`)
      .then((r) => r.json())
      .then(setSeasonPerformance)
      .catch(() => {});
    fetch(`${API_BASE}/season/transactions`)
      .then((r) => r.json())
      .then(setSeasonTxns)
      .catch(() => {});
    fetch(`${API_BASE}/season/user-team-indices`)
      .then((r) => r.json())
      .then(setUserTeamIndices)
      .catch(() => {});
    fetch(`${API_BASE}/season/tweet-labels`)
      .then((r) => r.json())
      .then(setTweetLabels)
      .catch(() => {});
  }, []);

  const currentTeam = useMemo(
    () => teams.find((t) => t.slug === selectedTeam),
    [teams, selectedTeam]
  );

  const rosterPlayers = useMemo(
    () =>
      selectedTeam
        ? players.filter((p) => p.main_team_slug === selectedTeam)
        : [],
    [players, selectedTeam]
  );

  const searchResults = useMemo(() => {
    if (!search.trim()) return [];
    const q = search.toLowerCase();
    return players
      .filter(
        (p) =>
          p.main_team_slug !== selectedTeam &&
          (p.first_name.toLowerCase().includes(q) ||
            p.last_name.toLowerCase().includes(q))
      )
      .slice(0, 20);
  }, [players, selectedTeam, search]);

  async function assignPlayer(playerId: string, teamSlug: string | null) {
    const url = teamSlug
      ? `${API_BASE}/players/${playerId}/team/${teamSlug}`
      : `${API_BASE}/players/${playerId}/team/none`;
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: teamSlug ? "assign" : "remove" }),
    });
    const updated = await fetch(`${API_BASE}/players`).then((r) => r.json());
    setPlayers(updated);
  }

  async function exportRoster(teamSlug: string) {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE}/teams/${teamSlug}/export`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${teamSlug}-roster.bin`;
      a.click();
      URL.revokeObjectURL(url);
      setStatus("Downloaded .bin");
    } catch (err: any) {
      setStatus(`Export failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function installRoster(teamSlug: string) {
    setLoading(true);
    setStatus(null);
    try {
      const res = await fetch(`${API_BASE}/teams/${teamSlug}/install`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setStatus(`Installed as "${data.saveName}" — ready to load in-game`);
    } catch (err: any) {
      setStatus(`Install failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  function teamLabel(teamSlug: string | null) {
    if (!teamSlug) return "FA";
    const t = teams.find((x) => x.slug === teamSlug);
    return t ? t.abbrev : "?";
  }

  // Season helpers
  const seasonTeamMap = useMemo(() => {
    const map = new Map<number, SeasonTeam>();
    for (const t of seasonTeams) {
      map.set(t.record, t);
    }
    return map;
  }, [seasonTeams]);

  const seasonPlayersByProteam = useMemo(() => {
    const map = new Map<number, SeasonPlayer[]>();
    for (const p of seasonPlayers) {
      const arr = map.get(p.proteam) || [];
      arr.push(p);
      map.set(p.proteam, arr);
    }
    return map;
  }, [seasonPlayers]);

  const currentSeasonTeam = useMemo(
    () => (selectedSeasonTeam !== null ? seasonTeamMap.get(selectedSeasonTeam) : null),
    [seasonTeamMap, selectedSeasonTeam]
  );

  const currentSeasonRoster = useMemo(
    () =>
      selectedSeasonTeam !== null
        ? seasonPlayersByProteam.get(selectedSeasonTeam + 1) || []
        : [],
    [seasonPlayersByProteam, selectedSeasonTeam]
  );

  const nhlSeasonTeams = useMemo(
    () => seasonTeams.filter((t) => t.record < 30),
    [seasonTeams]
  );

  const userTeamRecords = useMemo(
    () => new Set(userTeamIndices),
    [userTeamIndices]
  );

  const perfByRecord = useMemo(() => {
    const map = new Map<number, SeasonPerformanceEntry>();
    for (const p of seasonPerformance) map.set(p.record, p);
    return map;
  }, [seasonPerformance]);

  const sortEvents = useMemo(
    () => [...seasonEvents].sort((a, b) => a.day - b.day || a.id - b.id),
    [seasonEvents]
  );

  function tweetText(key: string): string {
    return tweetLabels[key] ?? key;
  }

  function scheduleTeamName(record: number | null): string {
    if (record === null) return "?";
    return seasonTeamMap.get(record)?.abbrev ?? `#${record}`;
  }

  return (
    <div className="App">
      <h1>NHL Legacy Fantasy</h1>

      <nav className="tab-bar">
        <button
          className={tab === "roster" ? "active" : ""}
          onClick={() => setTab("roster")}
        >
          Roster Editor
        </button>
        <button
          className={tab === "season" ? "active" : ""}
          onClick={() => setTab("season")}
        >
          Season Viewer
        </button>
      </nav>

      {status && (
        <div className="status-bar">
          {status}
          <button onClick={() => setStatus(null)}>x</button>
        </div>
      )}

      {tab === "roster" && (
        <>
          <section>
            <h2>Teams</h2>
            <ul className="team-list">
              {teams.map((team) => (
                <li key={team.slug}>
                  <span>
                    {team.city} {team.full_name.replace(team.city, "").trim()} ({team.abbrev})
                  </span>
                  <div className="team-actions">
                    <button onClick={() => setSelectedTeam(team.slug)}>Roster</button>
                    <button disabled={loading} onClick={() => exportRoster(team.slug)}>
                      Export .bin
                    </button>
                    <button disabled={loading} onClick={() => installRoster(team.slug)}>
                      Install
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {selectedTeam && currentTeam && (
            <section className="roster-panel">
              <h2>
                {currentTeam.full_name} Roster ({rosterPlayers.length} players)
                <button className="close-btn" onClick={() => setSelectedTeam(null)}>
                  Close
                </button>
              </h2>
              {rosterPlayers.length === 0 ? (
                <p className="empty">No players assigned yet.</p>
              ) : (
                <ul className="player-list">
                  {rosterPlayers.map((player) => (
                    <li key={player.id}>
                      <span>{player.first_name} {player.last_name}</span>
                      <button onClick={() => assignPlayer(player.id, null)}>Remove</button>
                    </li>
                  ))}
                </ul>
              )}
              <h3>Add player</h3>
              <input
                type="text"
                placeholder="Search players..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              {searchResults.length > 0 && (
                <ul className="player-list search-results">
                  {searchResults.map((player) => (
                    <li key={player.id}>
                      <span>
                        {player.first_name} {player.last_name}{" "}
                        <small>({teamLabel(player.main_team_slug)})</small>
                      </span>
                      <button onClick={() => assignPlayer(player.id, selectedTeam)}>
                        Assign
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}

      {tab === "season" && (
        <>
          <section className="season-header">
            <h2>Season Mode — Day {seasonDay}</h2>
            {seasonGmStates.length > 0 && (
              <p className="season-gms">
                {seasonGmStates.length} GM{seasonGmStates.length !== 1 ? "s" : ""}:{" "}
                {seasonGmStates
                  .slice(0, 5)
                  .map((g) => `${g.gm_first_name} ${g.gm_last_name}`)
                  .join(", ")}
                {seasonGmStates.length > 5 ? `, +${seasonGmStates.length - 5} more` : ""}
              </p>
            )}
          </section>

          <section>
            <h2>Teams</h2>
            <ul className="team-list">
              {nhlSeasonTeams.map((team) => (
                <li key={team.record}>
                  <span>
                    {team.city} {team.full_name?.replace(team.city, "").trim()}{" "}
                    ({team.abbrev})
                  </span>
                  <div className="team-actions">
                    <button onClick={() => setSelectedSeasonTeam(team.record)}>Roster</button>
                    <span className="player-count">
                      {seasonPlayersByProteam.get(team.record + 1)?.length ?? 0} players
                    </span>
                    {userTeamRecords.has(team.record) && (
                      <span className="user-badge">User</span>
                    )}
                    {perfByRecord.has(team.record) && (
                      <span className="perf-badge" title={`Budget: ${(perfByRecord.get(team.record)!.budget_score / 1e6).toFixed(1)}M  Score: ${(perfByRecord.get(team.record)!.performance_score / 1e6).toFixed(1)}M`}>
                        {(perfByRecord.get(team.record)!.performance_score / 1e6).toFixed(1)}M
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {selectedSeasonTeam !== null && currentSeasonTeam && (
            <section className="roster-panel">
              <h2>
                {currentSeasonTeam.city} Roster ({currentSeasonRoster.length} players)
                <button className="close-btn" onClick={() => setSelectedSeasonTeam(null)}>
                  Close
                </button>
              </h2>
              <ul className="player-list">
                {currentSeasonRoster.map((player) => (
                  <li key={player.record}>
                    <span>{player.first_name} {player.last_name}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section>
            <h2>Calendar ({sortEvents.length} events)</h2>
            {sortEvents.length === 0 ? (
              <p className="empty">No events yet.</p>
            ) : (
              <ul className="event-list">
                {sortEvents.slice(0, 20).map((event) => (
                  <li key={event.id}>
                    <span className="event-day">Day {event.day}</span>
                    <span className="event-text">{tweetText(event.text_key)}</span>
                  </li>
                ))}
                {sortEvents.length > 20 && (
                  <li className="event-more">+{sortEvents.length - 20} more events</li>
                )}
              </ul>
            )}
          </section>

          <section>
            <h2>Team Performance</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Team</th>
                  <th>GM</th>
                  <th>Day</th>
                  <th>Budget Score</th>
                  <th>Perf Score</th>
                </tr>
              </thead>
              <tbody>
                {seasonPerformance
                  .sort((a, b) => b.performance_score - a.performance_score)
                  .map((p) => {
                    const t = seasonTeamMap.get(p.record);
                    return (
                      <tr key={p.record}>
                        <td>{t?.abbrev ?? `Team ${p.record}`}</td>
                        <td>{p.gm_first_name} {p.gm_last_name}</td>
                        <td>{p.current_day}</td>
                        <td>{(p.budget_score / 1e6).toFixed(1)}M</td>
                        <td>{(p.performance_score / 1e6).toFixed(1)}M</td>
                      </tr>
                    );
                  })}
              </tbody>
            </table>
          </section>

          <section>
            <h2>Schedule ({seasonSchedule.length} games)</h2>
            <div className="schedule-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Home</th>
                    <th>Away</th>
                    <th>Score</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {seasonSchedule.map((s) => (
                    <tr key={s.id}>
                      <td>{s.game_index}</td>
                      <td>{scheduleTeamName(s.home_team ?? null)}</td>
                      <td>{scheduleTeamName(s.away_team ?? null)}</td>
                      <td>{s.home_goals}-{s.away_goals}</td>
                      <td>{s.is_future ? "Future" : "Played"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section>
            <h2>Transactions ({seasonTxns.length})</h2>
            <div className="schedule-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Day</th>
                    <th>Player</th>
                    <th>Team</th>
                    <th>With</th>
                    <th>Type</th>
                  </tr>
                </thead>
                <tbody>
                  {seasonTxns.map((t, i) => (
                    <tr key={i}>
                      <td>{t.event_index}</td>
                      <td>{t.day}</td>
                      <td>{t.player_name ?? "?"}</td>
                      <td>{t.team_name ?? "?"}</td>
                      <td>{t.with_team_name ?? "—"}</td>
                      <td>{t.sub_type === 7 ? "Trade-Out" : t.sub_type === 6 ? "Trade-In" : t.sub_type === 8 ? "Signing" : t.sub_type === 16 ? "Extend" : `sub${t.sub_type}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="placeholder-section">
            <h2>Standings (W-L-OTL-PTS)</h2>
            <p className="empty">Standings computed from game results — coming soon.</p>
          </section>

          <section className="placeholder-section">
            <h2>Depth Charts / Captaincy / Jersey Numbers</h2>
            <p className="empty">Table identification in progress.</p>
          </section>
        </>
      )}
    </div>
  );
}

export default App;
