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

const API_BASE = "/api";

function App() {
  const [teams, setTeams] = useState<Team[]>([]);
  const [players, setPlayers] = useState<Player[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

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

  return (
    <div className="App">
      <h1>NHL Legacy Fantasy</h1>

      {status && (
        <div className="status-bar">
          {status}
          <button onClick={() => setStatus(null)}>x</button>
        </div>
      )}

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
                  <span>
                    {player.first_name} {player.last_name}
                  </span>
                  <button onClick={() => assignPlayer(player.id, null)}>
                    Remove
                  </button>
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
    </div>
  );
}

export default App;
