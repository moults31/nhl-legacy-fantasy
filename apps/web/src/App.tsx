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
    () => seasonTeams.filter((t) => t.record < 32),
    [seasonTeams]
  );

  const sortEvents = useMemo(
    () => [...seasonEvents].sort((a, b) => a.day - b.day || a.id - b.id),
    [seasonEvents]
  );

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
                {sortEvents.map((event) => (
                  <li key={event.id}>
                    <span className="event-day">Day {event.day}</span>
                    <span className="event-text">{event.text_key}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default App;
