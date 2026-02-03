import { useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000'

const styles = {
    full: { fontFamily: 'Inter, Arial, sans-serif', background: '#f7fafc', minHeight: '100vh', padding: 24 },
    container: { maxWidth: 1200, margin: '0 auto' },
    headerRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 },
    brand: { display: 'flex', alignItems: 'center', gap: 12 },
    logo: { width: 44, height: 44, borderRadius: 8, background: '#2b6ef6', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 },
    title: { fontSize: 18, fontWeight: 700 },
    heroSub: { color: '#65748b', fontSize: 13 },
    loginWrap: { display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '70vh' },
    loginBox: { background: 'white', padding: 28, borderRadius: 10, boxShadow: '0 6px 22px rgba(15,23,42,0.08)', width: 420 },
    field: { width: '100%', padding: 10, marginBottom: 10, borderRadius: 8, border: '1px solid #eee' },
    btnPrimary: { background: '#2b6ef6', color: 'white', padding: '10px 14px', borderRadius: 8, cursor: 'pointer', border: 'none' },
    muted: { color: '#64748b', fontSize: 13 },
    mainGrid: { display: 'grid', gridTemplateColumns: '1fr 420px', gap: 20 },
    card: { background: 'white', borderRadius: 10, padding: 16, boxShadow: '0 6px 18px rgba(15,23,42,0.06)' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { textAlign: 'left', padding: '10px 12px', fontSize: 13, color: '#334155' },
    td: { padding: '12px', borderTop: '1px solid #f1f5f9', verticalAlign: 'top' }
}

export default function Admin() {
    // Keep token and protected data in memory only
    const [adminToken, setAdminToken] = useState(null)
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [authError, setAuthError] = useState(null)
    const [loading, setLoading] = useState(false)

    // Protected data loaded after login
    const [events, setEvents] = useState([])
    const [requests, setRequests] = useState([])
    const [q, setQ] = useState('')

    async function loadProtected(token) {
        setLoading(true)
        try {
            const [er, rr] = await Promise.all([
                fetch(`${API_BASE}/api/events`, { headers: { 'X-Admin-Token': token } }).then(r => r.json()),
                fetch(`${API_BASE}/api/ticket-requests`, { headers: { 'X-Admin-Token': token } }).then(r => r.json())
            ])
            setEvents(Array.isArray(er) ? er : (er.events || []))
            setRequests(Array.isArray(rr) ? rr : (rr.requests || []))
        } catch (err) {
            console.error('loadProtected', err)
            setAuthError('Failed to load admin data')
        } finally {
            setLoading(false)
        }
    }

    const doLogin = async (e) => {
        e && e.preventDefault()
        setAuthError(null)
        setLoading(true)
        try {
            const res = await fetch(`${API_BASE}/api/admin/login`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            })
            const j = await res.json()
            if (!res.ok) {
                setAuthError(j.error || 'Login failed')
                setLoading(false)
                return
            }
            // keep token in-memory only
            setAdminToken(j.token)
            setUsername('')
            setPassword('')
            // load protected data
            await loadProtected(j.token)
        } catch (err) {
            console.error('login', err)
            setAuthError('Network error')
            setLoading(false)
        }
    }

    const doLogout = async () => {
        const token = adminToken
        try {
            await fetch(`${API_BASE}/api/admin/logout`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }) })
        } catch (e) {
            // ignore network errors on logout
        }
        // clear in-memory state and return to login
        setAdminToken(null)
        setEvents([])
        setRequests([])
        setAuthError(null)
    }

    const toggle = async (id, payload) => {
        if (!adminToken) return
        const headers = { 'Content-Type': 'application/json', 'X-Admin-Token': adminToken }
        await fetch(`${API_BASE}/api/events/${id}`, { method: 'PATCH', headers, body: JSON.stringify(payload) })
        await loadProtected(adminToken)
    }

    const filtered = requests.filter(r => r.email.toLowerCase().includes(q.toLowerCase()) || (r.event_title || '').toLowerCase().includes(q.toLowerCase()))

    // If not logged in show credentials page first
    if (!adminToken) {
        return (
            <div style={styles.full}>
                <div style={styles.container}>
                    <div style={styles.headerRow}>
                        <div style={styles.brand}><div style={styles.logo}>EP</div><div><div style={styles.title}>EventPulse Admin</div><div style={styles.heroSub}>Manage events, leads and site content</div></div></div>
                    </div>
                </div>

                <div style={styles.loginWrap}>
                    <div style={styles.loginBox}>
                        <h3 style={{ marginTop: 0 }}>Sign in</h3>
                        <form onSubmit={doLogin}>
                            <input className="admin-field" placeholder="username" value={username} onChange={e => setUsername(e.target.value)} style={styles.field} />
                            <input className="admin-field" type="password" placeholder="password" value={password} onChange={e => setPassword(e.target.value)} style={styles.field} />
                            {authError && <div style={{ color: 'red', marginBottom: 8 }}>{authError}</div>}
                            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                                <button type="submit" style={styles.btnPrimary} disabled={loading}>{loading ? 'Signing in...' : 'Sign in'}</button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        )
    }

    // Logged in: show admin dashboard
    return (
        <div style={styles.full}>
            <div style={styles.container}>
                <div style={styles.headerRow}>
                    <div style={styles.brand}><div style={styles.logo}>EP</div><div><div style={styles.title}>EventPulse Admin</div><div style={styles.heroSub}>Manage events, leads and site content</div></div></div>
                    <div>
                        <button onClick={doLogout} style={styles.btnPrimary}>Log out</button>
                    </div>
                </div>

                {loading && <div style={{ padding: 12 }}>Loading...</div>}

                <main style={styles.mainGrid}>
                    <section style={styles.card}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                            <div>
                                <h3 style={{ margin: 0 }}>Events</h3>
                                <div style={styles.muted}>{events.length} total</div>
                            </div>
                        </div>

                        <table style={styles.table}>
                            <thead>
                                <tr>
                                    <th style={styles.th}>Title</th>
                                    <th style={styles.th}>Source</th>
                                    <th style={styles.th}>Featured</th>
                                    <th style={styles.th}>Active</th>
                                    <th style={styles.th}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {events.map(ev => (
                                    <tr key={ev.id}>
                                        <td style={styles.td}>{ev.title}</td>
                                        <td style={styles.td}><div style={styles.muted}>{ev.source}</div></td>
                                        <td style={styles.td}>{ev.featured ? 'Yes' : 'No'}</td>
                                        <td style={styles.td}>{ev.active ? 'Yes' : 'No'}</td>
                                        <td style={styles.td}>
                                            <button onClick={() => toggle(ev.id, { featured: !ev.featured })} style={{ marginRight: 8 }}> {ev.featured ? 'Unfeature' : 'Feature'}</button>
                                            <button onClick={() => toggle(ev.id, { active: !ev.active })}>{ev.active ? 'Deactivate' : 'Activate'}</button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </section>

                    <aside style={styles.card}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h3 style={{ margin: 0 }}>Ticket Requests</h3>
                            <a href={`${API_BASE}/api/ticket-requests.csv`} style={styles.muted}>Export CSV</a>
                        </div>

                        <div style={{ marginTop: 12, marginBottom: 12 }}>
                            <input placeholder="Search email or event" style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #eee' }} value={q} onChange={e => setQ(e.target.value)} />
                        </div>

                        <div style={{ maxHeight: 560, overflow: 'auto' }}>
                            <table style={styles.table}>
                                <thead>
                                    <tr>
                                        <th style={styles.th}>Email</th>
                                        <th style={styles.th}>Confirmed</th>
                                        <th style={styles.th}>Event</th>
                                        <th style={styles.th}>Created</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filtered.map(rq => (
                                        <tr key={rq.id}>
                                            <td style={styles.td}>{rq.email}</td>
                                            <td style={styles.td}>{rq.confirmed ? 'Yes' : 'No'}</td>
                                            <td style={styles.td}>{rq.event_title || (rq.event_url ? 'External' : '')}</td>
                                            <td style={styles.td}><div style={styles.muted}>{rq.created_at}</div></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                            {filtered.length === 0 && <div style={{ padding: 12, color: '#666' }}>No requests</div>}
                        </div>
                    </aside>
                </main>

                {authError && <div style={{ marginTop: 12, color: 'red' }}>{authError}</div>}
            </div>
        </div>
    )
}
