import { useEffect, useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:5000'

function formatDate(s) {
    if (!s) return ''
    try {
        const d = new Date(s)
        if (!isNaN(d.getTime())) return d.toLocaleString()
        // try to clean common ordinal suffixes and parse again
        const cleaned = String(s).replace(/(\d+)(st|nd|rd|th)/gi, "$1").replace(/–|—/g, '-').split('-')[0].trim()
        const d2 = new Date(cleaned)
        if (!isNaN(d2.getTime())) return d2.toLocaleString()
        return String(s)
    } catch {
        return String(s)
    }
}

function truncate(s, n = 140) {
    if (!s) return ''
    return s.length > n ? s.slice(0, n - 1).trim() + '…' : s
}

export default function Home() {
    const [events, setEvents] = useState([])
    const [loading, setLoading] = useState(true)
    const [query, setQuery] = useState('')
    const [page, setPage] = useState(1)
    const perPage = 12
    // tag filters (chips)
    const [selectedTags, setSelectedTags] = useState([])
    const toggleTag = (tag) => {
        setPage(1)
        setSelectedTags(prev => {
            if (prev.includes(tag)) return prev.filter(t => t !== tag)
            return [...prev, tag]
        })
    }

    useEffect(() => {
        fetch(`${API_BASE}/api/events`)
            .then(r => r.json())
            .then(data => {
                setEvents(data || [])
                setLoading(false)
            })
            .catch(err => {
                console.error(err)
                setLoading(false)
            })
    }, [])

    // Filters state (left column)
    const [timeframe, setTimeframe] = useState('any')
    const [sources, setSources] = useState({})

    useEffect(() => {
        // initialize sources from events
        const s = {}
        for (const ev of events) if (ev.source) s[ev.source] = true
        setSources(s)
    }, [events])

    const toggleSource = (k) => setSources(prev => ({ ...prev, [k]: !prev[k] }))

    // determine if an event matches current filters (query, timeframe, sources)
    const filtered = events.filter(e => {
        // text query
        if (query) {
            const q = query.toLowerCase()
            if (!((e.title || '').toLowerCase().includes(q) || (e.description || '').toLowerCase().includes(q) || (e.venue || '').toLowerCase().includes(q))) return false
        }

        // source filter: if sources list exists and the specific source is unchecked, exclude
        const srcKeys = Object.keys(sources)
        if (srcKeys.length > 0) {
            // if the event has a source and that source is explicitly false, filter it out
            if (e.source && sources.hasOwnProperty(e.source) && !sources[e.source]) return false
        }

        // timeframe filter
        if (timeframe && timeframe !== 'any') {
            const s = e.start_time || e.start || e.date || e.datetime
            if (!s) return false

            const parseDate = (str) => {
                if (!str) return null
                let d = new Date(str)
                if (!isNaN(d.getTime())) return d
                const cleaned = String(str).replace(/(\d+)(st|nd|rd|th)/gi, "$1").replace(/–|—/g, '-').split('-')[0].trim()
                d = new Date(cleaned)
                if (!isNaN(d.getTime())) return d
                return null
            }

            const d = parseDate(s)
            if (!d) return false

            const now = new Date()
            const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate())
            const endOfDay = new Date(startOfDay); endOfDay.setDate(startOfDay.getDate() + 1)

            if (timeframe === 'today') {
                // same calendar date
                const evDay = new Date(d.getFullYear(), d.getMonth(), d.getDate())
                if (evDay.getTime() !== startOfDay.getTime()) return false
            } else if (timeframe === 'week') {
                // This weekend: upcoming Saturday and Sunday
                const day = now.getDay() // 0 Sun .. 6 Sat
                const daysUntilSat = (6 - day + 7) % 7
                const sat = new Date(now); sat.setDate(now.getDate() + daysUntilSat); sat.setHours(0, 0, 0, 0)
                const sun = new Date(sat); sun.setDate(sat.getDate() + 1); sun.setHours(23, 59, 59, 999)
                if (d < sat || d > sun) return false
            } else if (timeframe === 'next') {
                // Next week: the 7-day window after this weekend
                const day = now.getDay()
                const daysUntilSat = (6 - day + 7) % 7
                const afterWeekend = new Date(now); afterWeekend.setDate(now.getDate() + daysUntilSat + 2); afterWeekend.setHours(0, 0, 0, 0)
                const end = new Date(afterWeekend); end.setDate(afterWeekend.getDate() + 6); end.setHours(23, 59, 59, 999)
                if (d < afterWeekend || d > end) return false
            }
        }

        return true
    })

    // apply tag/chip filters
    const tagFiltered = filtered.filter(e => {
        if (!selectedTags || selectedTags.length === 0) return true
        const cat = (e.category || '').toString()
        for (const t of selectedTags) {
            if (cat && cat.toLowerCase().includes(t.toLowerCase())) return true
            if ((e.title || '').toLowerCase().includes(t.toLowerCase())) return true
            if ((e.description || '').toLowerCase().includes(t.toLowerCase())) return true
        }
        return false
    })

    const total = tagFiltered.length
    const pages = Math.max(1, Math.ceil(total / perPage))
    const display = tagFiltered.slice((page - 1) * perPage, page * perPage)

    const [modalOpen, setModalOpen] = useState(false)
    const [modalEvent, setModalEvent] = useState(null)
    const [email, setEmail] = useState('')
    const [consent, setConsent] = useState(false)
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState(null)

    const openModal = (ev) => {
        setModalEvent(ev)
        setEmail('')
        setConsent(false)
        setError(null)
        setModalOpen(true)
    }

    const submitRequest = async () => {
        if (!email) { setError('Email is required'); return }
        setSubmitting(true)
        try {
            const payload = { email, consent, event_id: modalEvent.id, event_url: modalEvent.original_url }
            const r = await fetch(`${API_BASE}/api/ticket-request`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
            const j = await r.json()
            if (!r.ok) {
                setError(j.error || 'Failed')
                setSubmitting(false)
                return
            }
            window.location.href = j.redirect || modalEvent.original_url
        } catch (err) {
            setError('Network error')
            setSubmitting(false)
        }
    }



    const cards = display

    return (
        <div style={{ fontFamily: 'Inter, system-ui, -apple-system, sans-serif', background: '#fafafa', minHeight: '100vh' }}>
            <header style={{ borderBottom: '1px solid #eee', background: '#fff' }}>
                <div style={{ maxWidth: 1200, margin: '0 auto', padding: '18px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div style={{ width: 40, height: 40, borderRadius: 8, background: '#6b46c1', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>EP</div>
                        <div>
                            <div style={{ fontWeight: 700 }}>EventPulse</div>
                        </div>
                    </div>
                    <nav>
                        <a href="/admin" style={{ marginRight: 12 }}>Admin</a>
                        <a href="#">Discover</a>
                    </nav>
                </div>
            </header>

            <main style={{ maxWidth: 1200, margin: '24px auto', padding: '0 16px' }}>
                <section style={{ background: '#fff', borderRadius: 10, padding: '40px 32px', textAlign: 'center', boxShadow: '0 6px 18px rgba(15,23,42,0.04)', marginBottom: 20 }}>
                    <h1 style={{ margin: 0, fontSize: 42, lineHeight: 1.05 }}>Discover Global Events<br /><span style={{ color: '#6b46c1' }}>All in One Place</span></h1>
                    <p style={{ color: '#666', marginTop: 12 }}>We scrape 50+ platforms daily to bring you the best concerts, workshops, sports, and meetups in one clean feed.</p>

                    <div style={{ marginTop: 18, display: 'flex', justifyContent: 'center' }}>
                        <input placeholder="Search concerts, yoga, art, or workshops..." value={query} onChange={e => { setQuery(e.target.value); setPage(1) }} style={{ width: '60%', padding: '12px 16px', borderRadius: 999, border: '1px solid #eee' }} />
                    </div>
                    <div style={{ marginTop: 12, display: 'flex', justifyContent: 'center', gap: 8, flexWrap: 'wrap' }}>
                        {['Music', 'Arts', 'Food & Drink', 'Sports', 'Wellness', 'Tech', 'Nightlife'].map(tag => {
                            const active = selectedTags.includes(tag)
                            return (
                                <button key={tag} onClick={() => toggleTag(tag)} style={{ borderRadius: 999, padding: '6px 10px', border: '1px solid #eee', background: active ? '#6b46c1' : '#fff', color: active ? '#fff' : '#000', cursor: 'pointer' }}>{tag}</button>
                            )
                        })}
                    </div>
                </section>

                <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 20 }}>
                    <aside style={{ position: 'sticky', top: 20, alignSelf: 'start' }}>
                        <div style={{ background: '#fff', padding: 16, borderRadius: 8, boxShadow: '0 6px 18px rgba(15,23,42,0.04)' }}>
                            <h4 style={{ marginTop: 0 }}>TIME FRAME</h4>
                            <div>
                                <label style={{ display: 'block', marginBottom: 8 }}><input type="radio" name="tf" checked={timeframe === 'any'} onChange={() => setTimeframe('any')} /> Any Time</label>
                                <label style={{ display: 'block', marginBottom: 8 }}><input type="radio" name="tf" checked={timeframe === 'today'} onChange={() => setTimeframe('today')} /> Today</label>
                                <label style={{ display: 'block', marginBottom: 8 }}><input type="radio" name="tf" checked={timeframe === 'week'} onChange={() => setTimeframe('week')} /> This Weekend</label>
                                <label style={{ display: 'block', marginBottom: 8 }}><input type="radio" name="tf" checked={timeframe === 'next'} onChange={() => setTimeframe('next')} /> Next Week</label>
                            </div>

                            <h4 style={{ marginTop: 16 }}>SOURCE</h4>
                            <div style={{ maxHeight: 220, overflow: 'auto' }}>
                                {Object.keys(sources).map(k => (
                                    <label key={k} style={{ display: 'block', marginBottom: 6 }}>
                                        <input type="checkbox" checked={!!sources[k]} onChange={() => toggleSource(k)} /> {k}
                                    </label>
                                ))}
                            </div>
                        </div>
                    </aside>

                    <section>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                            <h2 style={{ margin: 0 }}>Upcoming Events</h2>
                            <div style={{ color: '#666' }}>{!loading && <strong>{total}</strong>} results</div>
                        </div>

                        {loading && <div style={{ padding: 24, background: '#fff', borderRadius: 8 }}>Loading events...</div>}

                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
                            {cards.map(ev => (
                                <article key={ev.original_url} style={{ background: '#fff', borderRadius: 8, overflow: 'hidden', boxShadow: '0 6px 18px rgba(15,23,42,0.04)', display: 'flex', flexDirection: 'column', height: '100%' }}>
                                    <div style={{ height: 160, background: '#f3f4f6' }}>
                                        {ev.image_url ? (
                                            <img src={(ev.image_url && ev.image_url.startsWith('//')) ? ('https:' + ev.image_url) : ev.image_url} alt="poster" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                        ) : (
                                            <div style={{ width: '100%', height: '100%', background: 'linear-gradient(90deg, #f3f4f6, #f8fafc)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>No image</div>
                                        )}
                                    </div>
                                    <div style={{ padding: 12, display: 'flex', flexDirection: 'column', minHeight: 140, flex: '1 1 auto' }}>
                                        <div style={{ color: '#6b46c1', fontSize: 13 }}>{ev.category || ''}</div>
                                        <h3 style={{ margin: '6px 0' }}>{ev.title}</h3>
                                        <div style={{ color: '#666', fontSize: 13, marginBottom: 8 }}>{formatDate(ev.start_time)}</div>
                                        <div style={{ color: '#444', fontSize: 14, marginBottom: 8 }}>{truncate(ev.description, 80)}</div>
                                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 'auto' }}>
                                            <button onClick={() => openModal(ev)} style={{ background: '#2b6ef6', color: 'white', border: 'none', padding: '8px 10px', borderRadius: 6 }}>GET TICKETS</button>
                                            <div style={{ marginLeft: 'auto', color: '#888' }}>{ev.source}</div>
                                        </div>
                                    </div>
                                </article>
                            ))}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 20 }}>
                            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}>Prev</button>
                            <div>Page {page} / {pages}</div>
                            <button onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page >= pages}>Next</button>
                        </div>
                    </section>
                </div>
            </main>

            {modalOpen && modalEvent && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ background: '#fff', padding: 20, borderRadius: 8, width: 480, maxWidth: '92%' }}>
                        <h3>Get tickets — {modalEvent.title}</h3>
                        <p style={{ color: '#666' }}>{modalEvent.venue} — {formatDate(modalEvent.start_time)}</p>
                        <label style={{ display: 'block', marginTop: 8 }}>Email address</label>
                        <input value={email} onChange={e => setEmail(e.target.value)} style={{ width: '100%', padding: 8 }} placeholder="you@example.com" />
                        <label style={{ display: 'block', marginTop: 8 }}><input type="checkbox" checked={consent} onChange={e => setConsent(e.target.checked)} /> I agree to receive event information by email</label>
                        {error && <p style={{ color: 'red' }}>{error}</p>}
                        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
                            <button onClick={() => setModalOpen(false)} style={{ padding: '8px 10px' }}>Cancel</button>
                            <button onClick={submitRequest} disabled={submitting} style={{ background: '#0366d6', color: '#fff', padding: '8px 10px', border: 'none', borderRadius: 6 }}>{submitting ? 'Sending...' : 'Continue to tickets'}</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
