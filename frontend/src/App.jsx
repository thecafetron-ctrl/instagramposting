import { useState, useEffect, useRef } from 'react'
import './App.css'

const API_BASE = '/api'

// Color swatches for visual selection
const COLOR_SWATCHES = {
  black: { bg: '#0a0a0f', accent: '#787890' },
  purple: { bg: '#140a1f', accent: '#a070d0' },
  blue: { bg: '#0a1020', accent: '#60a0e0' },
  emerald: { bg: '#0a1812', accent: '#60c090' },
  copper: { bg: '#1a120a', accent: '#d0a060' },
  burgundy: { bg: '#1a0a10', accent: '#c07090' },
  gold: { bg: '#14100a', accent: '#d0b060' },
}

// Texture icons
const TEXTURE_ICONS = {
  stars: '✦',
  marble: '◇',
  logistics: '▣',
  mesh: '◈',
  minimal: '○',
  gradient: '▽',
}

function App() {
  const [contentTemplates, setContentTemplates] = useState([])
  const [colorThemes, setColorThemes] = useState([])
  const [textures, setTextures] = useState([])
  const [layouts, setLayouts] = useState([])
  
  const [selectedContentTemplate, setSelectedContentTemplate] = useState('problem_first')
  const [selectedColor, setSelectedColor] = useState('black')
  const [selectedTexture, setSelectedTexture] = useState('stars')
  const [selectedLayout, setSelectedLayout] = useState('centered_left_text')
  const [slideCount, setSlideCount] = useState(4)
  
  const [customTopic, setCustomTopic] = useState('')
  const [allowReuse, setAllowReuse] = useState(false)
  const [renderImages, setRenderImages] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [generatedPost, setGeneratedPost] = useState(null)
  const [posts, setPosts] = useState([])
  const [currentPage, setCurrentPage] = useState('generator') // generator, history, autopost, settings
  const [postingToIG, setPostingToIG] = useState(false)

  // Auto-post state
  const [autoPostSettings, setAutoPostSettings] = useState(null)
  const [scheduledPosts, setScheduledPosts] = useState([])
  const [savingSettings, setSavingSettings] = useState(false)

  // Leads state
  const [leads, setLeads] = useState([])
  const [leadStatuses, setLeadStatuses] = useState([])
  const [showLeadForm, setShowLeadForm] = useState(false)
  const [editingLead, setEditingLead] = useState(null)
  const [leadFilter, setLeadFilter] = useState('')

  // Post type state (carousel vs news)
  const [postType, setPostType] = useState('carousel') // 'carousel' or 'news'
  const [newsArticles, setNewsArticles] = useState([])
  const [selectedNewsIndex, setSelectedNewsIndex] = useState(0)
  const [customHeadline, setCustomHeadline] = useState('')
  const [newsCategory, setNewsCategory] = useState('SUPPLY CHAIN')
  const [generatedNewsPost, setGeneratedNewsPost] = useState(null)
  
  // News post options
  const [newsAccentColor, setNewsAccentColor] = useState('cyan')
  const [newsTimeRange, setNewsTimeRange] = useState('1d')
  const [newsAutoSelect, setNewsAutoSelect] = useState(false)

  useEffect(() => {
    fetchContentTemplates()
    fetchColorThemes()
    fetchTextures()
    fetchLayouts()
    fetchPosts()
    fetchAutoPostSettings()
    fetchLeads()
    fetchLeadStatuses()
    fetchScheduledPosts()
  }, [])

  const fetchContentTemplates = async () => {
    try {
      const res = await fetch(`${API_BASE}/templates`)
      const data = await res.json()
      setContentTemplates(data)
    } catch (err) {
      console.error('Failed to fetch content templates:', err)
    }
  }

  const fetchColorThemes = async () => {
    try {
      const res = await fetch(`${API_BASE}/color-themes`)
      const data = await res.json()
      setColorThemes(data)
    } catch (err) {
      console.error('Failed to fetch color themes:', err)
    }
  }

  const fetchTextures = async () => {
    try {
      const res = await fetch(`${API_BASE}/textures`)
      const data = await res.json()
      setTextures(data)
    } catch (err) {
      console.error('Failed to fetch textures:', err)
    }
  }

  const fetchLayouts = async () => {
    try {
      const res = await fetch(`${API_BASE}/layouts`)
      const data = await res.json()
      setLayouts(data)
    } catch (err) {
      console.error('Failed to fetch layouts:', err)
    }
  }

  const fetchPosts = async () => {
    try {
      const res = await fetch(`${API_BASE}/posts?limit=20`)
      const data = await res.json()
      setPosts(data)
    } catch (err) {
      console.error('Failed to fetch posts:', err)
    }
  }

  const fetchAutoPostSettings = async () => {
    try {
      const res = await fetch(`${API_BASE}/auto-post/settings`)
      const data = await res.json()
      setAutoPostSettings(data)
    } catch (err) {
      console.error('Failed to fetch auto-post settings:', err)
    }
  }

  const fetchScheduledPosts = async () => {
    try {
      const res = await fetch(`${API_BASE}/scheduled-posts`)
      const data = await res.json()
      setScheduledPosts(data)
    } catch (err) {
      console.error('Failed to fetch scheduled posts:', err)
    }
  }

  const fetchLeads = async (statusFilter = '') => {
    try {
      const url = statusFilter 
        ? `${API_BASE}/leads?status=${statusFilter}`
        : `${API_BASE}/leads`
      const res = await fetch(url)
      const data = await res.json()
      setLeads(data)
    } catch (err) {
      console.error('Failed to fetch leads:', err)
    }
  }

  const fetchLeadStatuses = async () => {
    try {
      const res = await fetch(`${API_BASE}/leads/statuses`)
      const data = await res.json()
      setLeadStatuses(data)
    } catch (err) {
      console.error('Failed to fetch lead statuses:', err)
    }
  }

  const createLead = async (leadData) => {
    try {
      const res = await fetch(`${API_BASE}/leads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(leadData),
      })
      const data = await res.json()
      fetchLeads(leadFilter)
      return data
    } catch (err) {
      console.error('Failed to create lead:', err)
    }
  }

  const updateLead = async (leadId, leadData) => {
    try {
      const res = await fetch(`${API_BASE}/leads/${leadId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(leadData),
      })
      const data = await res.json()
      fetchLeads(leadFilter)
      return data
    } catch (err) {
      console.error('Failed to update lead:', err)
    }
  }

  const updateLeadStatus = async (leadId, status, followUpDate = null) => {
    try {
      let url = `${API_BASE}/leads/${leadId}/status?status=${status}`
      if (followUpDate) {
        url += `&follow_up_date=${followUpDate}`
      }
      const res = await fetch(url, { method: 'PATCH' })
      const data = await res.json()
      fetchLeads(leadFilter)
      return data
    } catch (err) {
      console.error('Failed to update lead status:', err)
    }
  }

  const deleteLead = async (leadId) => {
    if (!confirm('Are you sure you want to delete this lead?')) return
    try {
      await fetch(`${API_BASE}/leads/${leadId}`, { method: 'DELETE' })
      fetchLeads(leadFilter)
    } catch (err) {
      console.error('Failed to delete lead:', err)
    }
  }

  const saveAutoPostSettings = async (newSettings) => {
    setSavingSettings(true)
    try {
      const res = await fetch(`${API_BASE}/auto-post/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newSettings),
      })
      const data = await res.json()
      setAutoPostSettings(data)
    } catch (err) {
      console.error('Failed to save auto-post settings:', err)
    } finally {
      setSavingSettings(false)
    }
  }

  const generateScheduleQueue = async () => {
    try {
      const res = await fetch(`${API_BASE}/scheduled-posts/generate-queue`, {
        method: 'POST',
      })
      const data = await res.json()
      fetchScheduledPosts()
      return data
    } catch (err) {
      console.error('Failed to generate schedule queue:', err)
    }
  }

  const deleteScheduledPost = async (id) => {
    try {
      await fetch(`${API_BASE}/scheduled-posts/${id}`, { method: 'DELETE' })
      fetchScheduledPosts()
    } catch (err) {
      console.error('Failed to delete scheduled post:', err)
    }
  }

  const postToInstagram = async (postId) => {
    // Auto-detect if we're on Railway or prompt for URL
    const isRailway = window.location.hostname.includes('railway.app')
    let publicUrl = ''
    
    if (isRailway) {
      // Use the Railway URL automatically
      publicUrl = window.location.origin
    } else {
      // Local development - need ngrok or similar
      const savedUrl = localStorage.getItem('instagram_public_url') || ''
      publicUrl = prompt(
        'Enter your public base URL for images:\n\n' +
        'Instagram requires publicly accessible image URLs.\n' +
        'Run: ngrok http 8000\n' +
        'Then paste the https URL here.\n\n' +
        'Leave empty to cancel:',
        savedUrl
      )
      
      if (!publicUrl) {
        alert('Instagram posting requires a public URL.\n\nUse ngrok to expose your local server.')
        return
      }
      
      localStorage.setItem('instagram_public_url', publicUrl)
    }
    
    setPostingToIG(true)
    try {
      const res = await fetch(`${API_BASE}/instagram/post`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          post_id: postId,
          base_url: publicUrl
        }),
      })
      
      // Check if response is JSON
      const contentType = res.headers.get('content-type')
      if (!contentType || !contentType.includes('application/json')) {
        const text = await res.text()
        console.error('Non-JSON response:', text.substring(0, 500))
        throw new Error(`Server error (${res.status}): ${text.substring(0, 200)}`)
      }
      
      const data = await res.json()
      
      if (data.status === 'success') {
        alert(`✅ Posted to Instagram!\n\nPost ID: ${data.instagram_post_id}`)
      } else {
        // More detailed error message
        let errorMsg = `❌ Instagram Error:\n\n${data.message || 'Unknown error'}`
        
        if (data.message?.includes('media container')) {
          errorMsg += '\n\n💡 This usually means Instagram cannot access the image URL. Try:\n'
          errorMsg += '1. Check if images are publicly accessible\n'
          errorMsg += '2. Use the diagnose endpoint: /api/instagram/diagnose/' + postId
        }
        
        alert(errorMsg)
        console.error('Instagram error details:', data)
      }
      return data
    } catch (err) {
      console.error('Failed to post to Instagram:', err)
      alert('Failed to post to Instagram: ' + err.message + '\n\nCheck browser console for details.')
    } finally {
      setPostingToIG(false)
    }
  }

  const schedulePost = async (options = {}) => {
    try {
      const res = await fetch(`${API_BASE}/scheduled-posts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(options),
      })
      const data = await res.json()
      fetchScheduledPosts()
      return data
    } catch (err) {
      console.error('Failed to schedule post:', err)
    }
  }

  // News functions
  const fetchNewsArticles = async (timeRange = newsTimeRange) => {
    try {
      const res = await fetch(`${API_BASE}/news/latest?count=10&time_range=${timeRange}`)
      const data = await res.json()
      if (data.news) {
        setNewsArticles(data.news)
      }
    } catch (err) {
      console.error('Failed to fetch news:', err)
    }
  }

  const generateNewsPost = async () => {
    setLoading(true)
    setError(null)
    setGeneratedNewsPost(null)

    try {
      const body = {
        category: newsCategory,
        accent_color: newsAccentColor,
        time_range: newsTimeRange,
        auto_select: newsAutoSelect,
      }
      
      // Use custom headline or selected news article (if not auto-selecting)
      if (customHeadline) {
        body.custom_headline = customHeadline
      } else if (!newsAutoSelect && newsArticles.length > 0) {
        body.selected_news_index = selectedNewsIndex
      }

      const res = await fetch(`${API_BASE}/news/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'News generation failed')
      }

      const post = await res.json()
      setGeneratedNewsPost(post)
      fetchPosts()
      setCustomHeadline('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const generatePost = async () => {
    setLoading(true)
    setError(null)
    setGeneratedPost(null)

    try {
      const res = await fetch(`${API_BASE}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          template_id: selectedContentTemplate,
          color_theme: selectedColor,
          texture: selectedTexture,
          layout: selectedLayout,
          slide_count: slideCount,
          topic: customTopic || null,
          allow_reuse: allowReuse,
          render_images: renderImages,
        }),
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Generation failed')
      }

      const post = await res.json()
      setGeneratedPost(post)
      fetchPosts()
      setCustomTopic('')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <div className="logo">
            <svg viewBox="0 0 200 60" className="logo-svg">
              <path d="M20 30 L40 20 L60 30 L40 40 Z" fill="currentColor" />
              <path d="M10 30 L40 15 L70 30 L40 45 Z" fill="none" stroke="currentColor" strokeWidth="2" />
            </svg>
            <span className="logo-text">STRUCTURE</span>
          </div>
          <nav className="nav">
            <button
              className={`nav-btn ${currentPage === 'generator' ? 'active' : ''}`}
              onClick={() => setCurrentPage('generator')}
            >
              Generator
            </button>
            <button
              className={`nav-btn ${currentPage === 'autopost' ? 'active' : ''}`}
              onClick={() => setCurrentPage('autopost')}
            >
              Auto Post
            </button>
            <button
              className={`nav-btn ${currentPage === 'history' ? 'active' : ''}`}
              onClick={() => setCurrentPage('history')}
            >
              History
            </button>
            <button
              className={`nav-btn ${currentPage === 'leads' ? 'active' : ''}`}
              onClick={() => setCurrentPage('leads')}
            >
              Leads
            </button>
            <button
              className={`nav-btn ${currentPage === 'settings' ? 'active' : ''}`}
              onClick={() => setCurrentPage('settings')}
            >
              Settings
            </button>
            <button
              className={`nav-btn ${currentPage === 'clipper' ? 'active' : ''}`}
              onClick={() => setCurrentPage('clipper')}
            >
              🎬 Clipper
            </button>
          </nav>
        </div>
      </header>

      <main className="main">
        {currentPage === 'generator' && (
          <div className="generator">
            <section className="controls-section">
              <h2 className="section-title">Generate Post</h2>

              {/* Post Type Selector */}
              <div className="post-type-selector">
                <label className="form-label">Post Type</label>
                <div className="post-type-buttons">
                  <button
                    className={`post-type-btn ${postType === 'carousel' ? 'active' : ''}`}
                    onClick={() => setPostType('carousel')}
                  >
                    <span className="post-type-icon">📊</span>
                    <span className="post-type-name">Information Carousel</span>
                    <span className="post-type-desc">4-10 slide educational content</span>
                  </button>
                  <button
                    className={`post-type-btn ${postType === 'news' ? 'active' : ''}`}
                    onClick={() => { setPostType('news'); fetchNewsArticles(); }}
                  >
                    <span className="post-type-icon">📰</span>
                    <span className="post-type-name">News Post</span>
                    <span className="post-type-desc">Single image with headline</span>
                  </button>
                </div>
              </div>

              {/* CAROUSEL POST OPTIONS */}
              {postType === 'carousel' && (
              <>
              {/* Visual Customization Section */}
              <div className="visual-section">
                <h3 className="subsection-title">Visual Style</h3>
                
                {/* Color Theme Selector */}
                <div className="selector-group">
                  <label className="form-label">Color Theme</label>
                  <div className="color-swatches">
                    {colorThemes.map((theme) => {
                      const swatch = COLOR_SWATCHES[theme.id] || { bg: '#0a0a0f', accent: '#808080' }
                      return (
                        <button
                          key={theme.id}
                          className={`color-swatch ${selectedColor === theme.id ? 'selected' : ''}`}
                          onClick={() => setSelectedColor(theme.id)}
                          style={{
                            background: `linear-gradient(135deg, ${swatch.bg} 0%, ${swatch.accent}33 100%)`,
                            borderColor: selectedColor === theme.id ? swatch.accent : 'transparent',
                          }}
                          title={theme.name}
                        >
                          <span className="swatch-dot" style={{ background: swatch.accent }}></span>
                          <span className="swatch-name">{theme.name}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>

                {/* Texture Selector */}
                <div className="selector-group">
                  <label className="form-label">Background Texture</label>
                  <div className="texture-grid">
                    {textures.map((texture) => (
                      <button
                        key={texture.id}
                        className={`texture-card ${selectedTexture === texture.id ? 'selected' : ''}`}
                        onClick={() => setSelectedTexture(texture.id)}
                      >
                        <span className="texture-icon">{TEXTURE_ICONS[texture.id] || '◇'}</span>
                        <span className="texture-name">{texture.name}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Layout Selector */}
                <div className="selector-group">
                  <label className="form-label">Layout Style</label>
                  <div className="layout-grid">
                    {layouts.map((layout) => (
                      <button
                        key={layout.id}
                        className={`layout-card ${selectedLayout === layout.id ? 'selected' : ''}`}
                        onClick={() => setSelectedLayout(layout.id)}
                      >
                        <span className="layout-name">{layout.name}</span>
                        <span className="layout-desc">{layout.description}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Slide Count Selector */}
                <div className="selector-group">
                  <label className="form-label">Number of Slides</label>
                  <div className="slide-count-selector">
                    {[4, 5, 6, 7, 8, 9, 10].map((count) => (
                      <button
                        key={count}
                        className={`slide-count-btn ${slideCount === count ? 'selected' : ''}`}
                        onClick={() => setSlideCount(count)}
                      >
                        {count}
                      </button>
                    ))}
                  </div>
                  <p className="form-hint">First and last slides stay the same. Middle slides expand.</p>
                </div>
              </div>

              {/* Content Template Selector */}
              <div className="selector-group">
                <label className="form-label">Content Template</label>
                <div className="content-template-grid">
                  {contentTemplates.map((template) => (
                    <button
                      key={template.id}
                      className={`content-template-card ${selectedContentTemplate === template.id ? 'selected' : ''}`}
                      onClick={() => setSelectedContentTemplate(template.id)}
                    >
                      <span className="template-icon">{template.icon}</span>
                      <div className="template-info">
                        <span className="template-name">{template.name}</span>
                        <span className="template-desc">{template.description}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Custom Topic (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="Leave empty for auto-discovery..."
                  value={customTopic}
                  onChange={(e) => setCustomTopic(e.target.value)}
                />
                <p className="form-hint">If empty, a fresh topic will be discovered automatically</p>
              </div>

              <div className="options-row">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={renderImages}
                    onChange={(e) => setRenderImages(e.target.checked)}
                  />
                  <span>Render slide images</span>
                </label>
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={allowReuse}
                    onChange={(e) => setAllowReuse(e.target.checked)}
                  />
                  <span>Allow topic reuse</span>
                </label>
              </div>

              <button
                className="btn btn-primary btn-lg generate-btn"
                onClick={generatePost}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="spinner"></span>
                    Generating...
                  </>
                ) : (
                  'Generate Carousel'
                )}
              </button>
              </>
              )}

              {/* NEWS POST OPTIONS */}
              {postType === 'news' && (
              <>
              <div className="news-section">
                <h3 className="subsection-title">📰 News Post Settings</h3>
                
                {/* Accent Color Selector */}
                <div className="selector-group">
                  <label className="form-label">Highlight Color</label>
                  <div className="accent-color-buttons">
                    {[
                      { id: 'cyan', color: '#00c8ff', name: 'Cyan' },
                      { id: 'blue', color: '#3b82f6', name: 'Blue' },
                      { id: 'green', color: '#22c55e', name: 'Green' },
                      { id: 'orange', color: '#f97316', name: 'Orange' },
                      { id: 'red', color: '#ef4444', name: 'Red' },
                      { id: 'yellow', color: '#eab308', name: 'Yellow' },
                      { id: 'pink', color: '#ec4899', name: 'Pink' },
                      { id: 'purple', color: '#a855f7', name: 'Purple' },
                    ].map(c => (
                      <button
                        key={c.id}
                        className={`accent-color-btn ${newsAccentColor === c.id ? 'active' : ''}`}
                        onClick={() => setNewsAccentColor(c.id)}
                        style={{ '--accent-color': c.color }}
                        title={c.name}
                      >
                        <span className="color-dot" style={{ background: c.color }}></span>
                        <span className="color-name">{c.name}</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Time Range Selector */}
                <div className="selector-group">
                  <label className="form-label">News Age</label>
                  <div className="time-range-buttons">
                    {[
                      { id: 'today', name: 'Today' },
                      { id: '1d', name: '24h' },
                      { id: '3d', name: '3 Days' },
                      { id: '1w', name: '1 Week' },
                      { id: '2w', name: '2 Weeks' },
                      { id: '4w', name: '1 Month' },
                      { id: 'anytime', name: 'Anytime' },
                    ].map(t => (
                      <button
                        key={t.id}
                        className={`time-btn ${newsTimeRange === t.id ? 'active' : ''}`}
                        onClick={() => { setNewsTimeRange(t.id); fetchNewsArticles(t.id); }}
                      >
                        {t.name}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Auto-Select Toggle */}
                <div className="selector-group">
                  <label className="toggle-label">
                    <input
                      type="checkbox"
                      checked={newsAutoSelect}
                      onChange={(e) => setNewsAutoSelect(e.target.checked)}
                    />
                    <span className="toggle-text">
                      <strong>AI Auto-Select</strong> - Let AI pick the most viral topic
                    </span>
                  </label>
                </div>
                
                {/* News Category */}
                <div className="selector-group">
                  <label className="form-label">Category Label</label>
                  <div className="category-buttons">
                    {['SUPPLY CHAIN', 'LOGISTICS', 'FREIGHT', 'SHIPPING', 'TECHNOLOGY', 'BREAKING'].map(cat => (
                      <button
                        key={cat}
                        className={`category-btn ${newsCategory === cat ? 'active' : ''}`}
                        onClick={() => setNewsCategory(cat)}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Custom Headline or Select from News */}
                {!newsAutoSelect && (
                <div className="selector-group">
                  <label className="form-label">Custom Headline (optional)</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Enter custom headline or select from latest news below..."
                    value={customHeadline}
                    onChange={(e) => setCustomHeadline(e.target.value)}
                  />
                </div>
                )}

                {/* Latest News Articles */}
                {!newsAutoSelect && (
                <div className="selector-group">
                  <div className="news-header">
                    <label className="form-label">Or Select from Latest News</label>
                    <button className="btn btn-sm" onClick={() => fetchNewsArticles()}>
                      🔄 Refresh
                    </button>
                  </div>
                  <div className="news-articles">
                    {newsArticles.length === 0 ? (
                      <div className="news-empty">
                        <p>Click "Refresh" to load latest supply chain news</p>
                      </div>
                    ) : (
                      newsArticles.map((article, idx) => (
                        <div
                          key={idx}
                          className={`news-article ${selectedNewsIndex === idx && !customHeadline ? 'selected' : ''}`}
                          onClick={() => { setSelectedNewsIndex(idx); setCustomHeadline(''); }}
                        >
                          <span className="news-category-tag">{article.category}</span>
                          <h4 className="news-title">{article.title}</h4>
                          {article.snippet && <p className="news-snippet">{article.snippet.slice(0, 120)}...</p>}
                          <span className="news-source">{article.source} {article.date && `• ${article.date}`}</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>
                )}
              </div>

              <button
                className="btn btn-primary btn-lg generate-btn"
                onClick={generateNewsPost}
                disabled={loading || (!newsAutoSelect && !customHeadline && newsArticles.length === 0)}
              >
                {loading ? (
                  <>
                    <span className="spinner"></span>
                    Generating...
                  </>
                ) : (
                  '📰 Generate News Post'
                )}
              </button>
              </>
              )}

              {error && (
                <div className="error-message">
                  {error}
                </div>
              )}
            </section>

            {generatedPost && (
              <section className="result-section animate-fade-in">
                <div className="result-header">
                  <h2 className="section-title">Generated Post</h2>
                  <span className="badge badge-success">Post #{generatedPost.id}</span>
                </div>

                <div className="topic-display">
                  <span className="topic-label">Topic:</span>
                  <span className="topic-text">{generatedPost.topic}</span>
                </div>

                <div className="slides-grid">
                  {generatedPost.slides && generatedPost.slides.map((slide) => (
                    <SlideCard
                      key={slide.number}
                      number={slide.number}
                      text={slide.text}
                      image={slide.image}
                      onCopy={copyToClipboard}
                    />
                  ))}
                </div>

                <div className="caption-section">
                  <div className="caption-header">
                    <h3>Caption</h3>
                    <button className="btn btn-secondary" onClick={() => copyToClipboard(generatedPost.caption)}>
                      Copy
                    </button>
                  </div>
                  <div className="caption-text">{generatedPost.caption}</div>
                </div>

                <div className="hashtags-section">
                  <div className="hashtags-header">
                    <h3>Hashtags</h3>
                    <button className="btn btn-secondary" onClick={() => copyToClipboard(generatedPost.hashtags)}>
                      Copy
                    </button>
                  </div>
                  <div className="hashtags-text">{generatedPost.hashtags}</div>
                </div>

                <div className="instagram-actions">
                  <button
                    className="btn btn-primary btn-lg instagram-btn"
                    onClick={() => postToInstagram(generatedPost.id)}
                    disabled={postingToIG}
                  >
                    {postingToIG ? 'Posting...' : '📸 Post to Instagram'}
                  </button>
                  <button
                    className="btn btn-secondary"
                    onClick={() => schedulePost({ post_id: generatedPost.id })}
                  >
                    📅 Schedule Post
                  </button>
                </div>
              </section>
            )}

            {/* NEWS POST RESULT */}
            {generatedNewsPost && (
              <section className="result-section news-result animate-fade-in">
                <div className="result-header">
                  <h2 className="section-title">📰 Generated News Post</h2>
                  <span className="badge badge-success">Post #{generatedNewsPost.id}</span>
                </div>

                <div className="news-post-preview">
                  <div className="news-category-display">
                    <span className="category-tag">{generatedNewsPost.category}</span>
                  </div>
                  <h3 className="news-headline-display">{generatedNewsPost.headline}</h3>
                  
                  {generatedNewsPost.image && (
                    <div className="news-image-preview">
                      <img 
                        src={`/images/${generatedNewsPost.image}`} 
                        alt="News Post"
                        className="news-preview-img"
                      />
                    </div>
                  )}
                </div>

                <div className="caption-section">
                  <div className="caption-header">
                    <h3>Caption</h3>
                    <button className="btn btn-secondary" onClick={() => copyToClipboard(generatedNewsPost.caption)}>
                      Copy
                    </button>
                  </div>
                  <div className="caption-text" dangerouslySetInnerHTML={{ __html: generatedNewsPost.caption?.replace(/\n/g, '<br />') }}></div>
                </div>

                <div className="instagram-actions">
                  <button
                    className="btn btn-primary btn-lg instagram-btn"
                    onClick={() => postToInstagram(generatedNewsPost.id)}
                    disabled={postingToIG}
                  >
                    {postingToIG ? 'Posting...' : '📸 Post to Instagram'}
                  </button>
                </div>
              </section>
            )}
          </div>
        )}

        {currentPage === 'autopost' && (
          <AutoPostPage
            settings={autoPostSettings}
            scheduledPosts={scheduledPosts}
            contentTemplates={contentTemplates}
            colorThemes={colorThemes}
            textures={textures}
            layouts={layouts}
            onSaveSettings={saveAutoPostSettings}
            onGenerateQueue={generateScheduleQueue}
            onDeleteScheduled={deleteScheduledPost}
            onSchedulePost={schedulePost}
            savingSettings={savingSettings}
          />
        )}

        {currentPage === 'history' && (
          <section className="history-section animate-fade-in">
            <h2 className="section-title">Post History</h2>
            {posts.length === 0 ? (
              <div className="empty-state">
                <p>No posts generated yet</p>
              </div>
            ) : (
              <div className="posts-list">
                {posts.map((post) => (
                  <div key={post.id} className="post-item">
                    <div className="post-item-header">
                      <span className="post-id">#{post.id}</span>
                      <span className="post-template">{post.template_id}</span>
                      <span className="post-date">{new Date(post.created_at).toLocaleDateString()}</span>
                    </div>
                    <div className="post-topic">{post.topic}</div>
                    <div className="post-actions">
                      <button
                        className="btn btn-secondary"
                        onClick={() => { setGeneratedPost(post); setCurrentPage('generator'); }}
                      >
                        View
                      </button>
                      <button
                        className="btn btn-primary"
                        onClick={() => postToInstagram(post.id)}
                      >
                        Post
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
            
            {/* Clip History */}
            <h2 className="section-title" style={{marginTop: '2rem'}}>🎬 Clip History</h2>
            <ClipHistorySection />
          </section>
        )}

        {currentPage === 'leads' && (
          <section className="leads-section animate-fade-in">
            <div className="leads-header">
              <h2 className="section-title">Lead Tracker</h2>
              <button 
                className="btn btn-primary"
                onClick={() => { setEditingLead(null); setShowLeadForm(true); }}
              >
                + Add Lead
              </button>
            </div>

            {/* Status Filter */}
            <div className="lead-filters">
              <button 
                className={`filter-btn ${leadFilter === '' ? 'active' : ''}`}
                onClick={() => { setLeadFilter(''); fetchLeads(''); }}
              >
                All
              </button>
              {leadStatuses.map(status => (
                <button
                  key={status.id}
                  className={`filter-btn ${leadFilter === status.id ? 'active' : ''}`}
                  style={{ borderColor: status.color }}
                  onClick={() => { setLeadFilter(status.id); fetchLeads(status.id); }}
                >
                  {status.label}
                </button>
              ))}
            </div>

            {/* Lead Form Modal */}
            {showLeadForm && (
              <div className="modal-overlay" onClick={() => setShowLeadForm(false)}>
                <div className="modal-content lead-form" onClick={e => e.stopPropagation()}>
                  <h3>{editingLead ? 'Edit Lead' : 'Add New Lead'}</h3>
                  <form onSubmit={async (e) => {
                    e.preventDefault()
                    const formData = new FormData(e.target)
                    const leadData = {
                      name: formData.get('name'),
                      instagram_handle: formData.get('instagram_handle') || null,
                      email: formData.get('email') || null,
                      phone: formData.get('phone') || null,
                      company: formData.get('company') || null,
                      status: formData.get('status') || 'new',
                      source: formData.get('source') || null,
                      notes: formData.get('notes') || null,
                      follow_up_date: formData.get('follow_up_date') || null,
                    }
                    if (editingLead) {
                      await updateLead(editingLead.id, leadData)
                    } else {
                      await createLead(leadData)
                    }
                    setShowLeadForm(false)
                    setEditingLead(null)
                  }}>
                    <div className="form-row">
                      <div className="form-group">
                        <label>Name *</label>
                        <input name="name" required defaultValue={editingLead?.name || ''} />
                      </div>
                      <div className="form-group">
                        <label>Instagram</label>
                        <input name="instagram_handle" placeholder="@username" defaultValue={editingLead?.instagram_handle || ''} />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>Email</label>
                        <input name="email" type="email" defaultValue={editingLead?.email || ''} />
                      </div>
                      <div className="form-group">
                        <label>Phone</label>
                        <input name="phone" defaultValue={editingLead?.phone || ''} />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>Company</label>
                        <input name="company" defaultValue={editingLead?.company || ''} />
                      </div>
                      <div className="form-group">
                        <label>Source</label>
                        <input name="source" placeholder="Instagram DM, Comment, etc." defaultValue={editingLead?.source || ''} />
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>Status</label>
                        <select name="status" defaultValue={editingLead?.status || 'new'}>
                          {leadStatuses.map(s => (
                            <option key={s.id} value={s.id}>{s.label}</option>
                          ))}
                        </select>
                      </div>
                      <div className="form-group">
                        <label>Follow-up Date</label>
                        <input name="follow_up_date" type="datetime-local" defaultValue={editingLead?.follow_up_date?.slice(0, 16) || ''} />
                      </div>
                    </div>
                    <div className="form-group full-width">
                      <label>Notes</label>
                      <textarea name="notes" rows="3" defaultValue={editingLead?.notes || ''}></textarea>
                    </div>
                    <div className="form-actions">
                      <button type="button" className="btn btn-secondary" onClick={() => { setShowLeadForm(false); setEditingLead(null); }}>
                        Cancel
                      </button>
                      <button type="submit" className="btn btn-primary">
                        {editingLead ? 'Save Changes' : 'Add Lead'}
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* Leads Table */}
            <div className="leads-table-container">
              <table className="leads-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Instagram</th>
                    <th>Contact</th>
                    <th>Status</th>
                    <th>Follow-up</th>
                    <th>Notes</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {leads.length === 0 ? (
                    <tr>
                      <td colSpan="7" className="empty-state">No leads yet. Add your first lead!</td>
                    </tr>
                  ) : (
                    leads.map(lead => {
                      const statusInfo = leadStatuses.find(s => s.id === lead.status) || { label: lead.status, color: '#6c757d' }
                      return (
                        <tr key={lead.id}>
                          <td>
                            <strong>{lead.name}</strong>
                            {lead.company && <div className="lead-company">{lead.company}</div>}
                          </td>
                          <td>
                            {lead.instagram_handle && (
                              <a href={`https://instagram.com/${lead.instagram_handle.replace('@', '')}`} target="_blank" rel="noopener noreferrer">
                                {lead.instagram_handle}
                              </a>
                            )}
                          </td>
                          <td>
                            {lead.email && <div className="lead-email">{lead.email}</div>}
                            {lead.phone && <div className="lead-phone">{lead.phone}</div>}
                          </td>
                          <td>
                            <select 
                              className="status-select"
                              value={lead.status}
                              style={{ borderColor: statusInfo.color, color: statusInfo.color }}
                              onChange={(e) => updateLeadStatus(lead.id, e.target.value)}
                            >
                              {leadStatuses.map(s => (
                                <option key={s.id} value={s.id}>{s.label}</option>
                              ))}
                            </select>
                          </td>
                          <td>
                            {lead.follow_up_date ? new Date(lead.follow_up_date).toLocaleDateString() : '-'}
                          </td>
                          <td className="lead-notes">
                            {lead.notes ? (lead.notes.length > 50 ? lead.notes.slice(0, 50) + '...' : lead.notes) : '-'}
                          </td>
                          <td>
                            <div className="lead-actions">
                              <button 
                                className="btn-icon" 
                                title="Edit"
                                onClick={() => { setEditingLead(lead); setShowLeadForm(true); }}
                              >
                                ✏️
                              </button>
                              <button 
                                className="btn-icon" 
                                title="Delete"
                                onClick={() => deleteLead(lead.id)}
                              >
                                🗑️
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {currentPage === 'settings' && (
          <section className="settings-section animate-fade-in">
            <h2 className="section-title">Settings</h2>
            <div className="settings-card">
              <div className="setting-item">
                <label className="form-label">Brand Name</label>
                <input type="text" className="form-input" defaultValue="STRUCTURE" disabled />
              </div>
              <div className="setting-item">
                <label className="form-label">API Status</label>
                <div className="status-indicator">
                  <span className="status-dot active"></span>
                  <span>Connected</span>
                </div>
              </div>
            </div>
          </section>
        )}

        {currentPage === 'clipper' && (
          <VideoClipperPage />
        )}
      </main>

      <footer className="footer">
        <p>STRUCTURE Instagram Carousel Generator v2.1.0</p>
      </footer>
    </div>
  )
}

function SlideCard({ number, text, image, onCopy }) {
  const [showText, setShowText] = useState(false)

  return (
    <div className="slide-card">
      <div className="slide-header">
        <span className="slide-number">Slide {number}</span>
        <div className="slide-actions">
          <button className={`slide-toggle ${showText ? 'active' : ''}`} onClick={() => setShowText(!showText)}>
            {showText ? 'Image' : 'Text'}
          </button>
          <button className="slide-copy" onClick={() => onCopy(text)}>
            Copy
          </button>
        </div>
      </div>
      <div className="slide-content">
        {showText ? (
          <pre className="slide-text">{text}</pre>
        ) : image ? (
          <img src={`/api/images/${image.split('/').pop()}`} alt={`Slide ${number}`} className="slide-image" />
        ) : (
          <div className="slide-placeholder">
            <span>No image rendered</span>
          </div>
        )}
      </div>
    </div>
  )
}

function ClipHistorySection() {
  const [clipHistory, setClipHistory] = useState([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    fetchClipHistory()
  }, [])
  
  const fetchClipHistory = async () => {
    try {
      const res = await fetch(`${API_BASE}/clipper/history`)
      const data = await res.json()
      setClipHistory(data.history || [])
    } catch (err) {
      console.error('Failed to fetch clip history:', err)
    } finally {
      setLoading(false)
    }
  }
  
  if (loading) return <p>Loading clip history...</p>
  
  if (clipHistory.length === 0) {
    return (
      <div className="empty-state">
        <p>No clips generated yet. Go to the Clipper tab to create some!</p>
      </div>
    )
  }
  
  return (
    <div className="clip-history">
      {clipHistory.map((job) => (
        <div key={job.job_id} className="clip-history-job">
          <div className="clip-history-header">
            <span className="job-date">{new Date(job.created_at).toLocaleDateString()}</span>
            {job.youtube_url && (
              <a href={job.youtube_url} target="_blank" rel="noopener noreferrer" className="source-link">
                📺 Source
              </a>
            )}
            <span className="clip-count">{job.clips?.length || 0} clips</span>
          </div>
          <div className="clip-history-clips">
            {job.clips?.map((clip, idx) => (
              <div key={idx} className="history-clip-card">
                <div className="clip-score">
                  <span className="score">{clip.virality_score}</span>
                  <span className="category">{clip.category}</span>
                </div>
                <video 
                  src={clip.video_url}
                  controls
                  preload="metadata"
                />
                <p className="clip-reason">{clip.virality_reason}</p>
                <div className="clip-actions">
                  <a 
                    href={clip.video_url}
                    download={`clip_${clip.index}.mp4`}
                    className="btn btn-sm btn-primary"
                  >
                    ⬇️ Download
                  </a>
                  <button 
                    className="btn btn-sm btn-secondary"
                    onClick={() => navigator.clipboard.writeText(clip.suggested_caption)}
                  >
                    📋 Copy Caption
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function VideoClipperPage() {
  const [clipperStatus, setClipperStatus] = useState(null)
  const [captionStyles, setCaptionStyles] = useState([])
  const [uploading, setUploading] = useState(false)
  const [currentJob, setCurrentJob] = useState(null)
  const [jobResult, setJobResult] = useState(null)
  const [pollInterval, setPollInterval] = useState(null)
  
  // Smart clipper state
  const [viralCandidates, setViralCandidates] = useState([])
  const [selectedCandidates, setSelectedCandidates] = useState(new Set())
  const [clipperPhase, setClipperPhase] = useState('input') // 'input', 'downloading', 'waiting', 'analyzing', 'select', 'rendering', 'done'
  const [smartResults, setSmartResults] = useState([])
  
  // Logs and estimates
  const [jobLogs, setJobLogs] = useState([])
  const [showLogs, setShowLogs] = useState(false)
  
  // Input mode
  const [inputMode, setInputMode] = useState('upload') // 'upload' or 'youtube'
  const [youtubeUrl, setYoutubeUrl] = useState('')
  
  // Load saved settings from localStorage
  const loadSavedSettings = () => {
    try {
      const saved = localStorage.getItem('clipper_settings')
      if (saved) return JSON.parse(saved)
    } catch (e) {}
    return null
  }
  
  const savedSettings = loadSavedSettings()
  
  // Settings (with saved defaults)
  const [numClips, setNumClips] = useState(savedSettings?.numClips ?? 10)
  const [minDuration, setMinDuration] = useState(savedSettings?.minDuration ?? 20)
  const [maxDuration, setMaxDuration] = useState(savedSettings?.maxDuration ?? 60)
  const [pauseThreshold, setPauseThreshold] = useState(savedSettings?.pauseThreshold ?? 0.7)
  const [captionStyle, setCaptionStyle] = useState(savedSettings?.captionStyle ?? 'default')
  const [whisperModel, setWhisperModel] = useState(savedSettings?.whisperModel ?? 'tiny')
  const [burnCaptions, setBurnCaptions] = useState(savedSettings?.burnCaptions ?? true)
  const [cropVertical, setCropVertical] = useState(savedSettings?.cropVertical ?? true)
  const [autoCenter, setAutoCenter] = useState(savedSettings?.autoCenter ?? true)
  
  // New style settings
  const [captionAnimation, setCaptionAnimation] = useState(savedSettings?.captionAnimation ?? 'karaoke')
  const [captionColor, setCaptionColor] = useState(savedSettings?.captionColor ?? '#FFFFFF')
  const [animationColor, setAnimationColor] = useState(savedSettings?.animationColor ?? '#FFFF00')
  const [titleStyle, setTitleStyle] = useState(savedSettings?.titleStyle ?? 'bold')
  const [titleColor, setTitleColor] = useState(savedSettings?.titleColor ?? '#FFFF00')
  const [videoVibe, setVideoVibe] = useState(savedSettings?.videoVibe ?? 'default')
  const [manualTopicSelect, setManualTopicSelect] = useState(savedSettings?.manualTopicSelect ?? false)
  const [captionSize, setCaptionSize] = useState(savedSettings?.captionSize ?? 80)
  const [showStylePanel, setShowStylePanel] = useState(false)
  const [clipEditRequests, setClipEditRequests] = useState({}) // {clipIndex: "edit request text"}
  const [addStockImages, setAddStockImages] = useState(savedSettings?.addStockImages ?? false)

  // Save settings to localStorage whenever they change
  useEffect(() => {
    const settings = {
      numClips, minDuration, maxDuration, pauseThreshold,
      captionStyle, whisperModel, burnCaptions, cropVertical, autoCenter,
      captionAnimation, captionColor, animationColor, titleStyle, titleColor,
      videoVibe, manualTopicSelect, captionSize, addStockImages
    }
    localStorage.setItem('clipper_settings', JSON.stringify(settings))
  }, [numClips, minDuration, maxDuration, pauseThreshold, captionStyle, whisperModel, burnCaptions, cropVertical, autoCenter, captionAnimation, captionColor, animationColor, titleStyle, titleColor, videoVibe, manualTopicSelect, captionSize, addStockImages])

  useEffect(() => {
    checkClipperStatus()
    fetchCaptionStyles()
    return () => {
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [])

  const checkClipperStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/clipper/status`)
      const data = await res.json()
      setClipperStatus(data)
    } catch (err) {
      console.error('Failed to check clipper status:', err)
      setClipperStatus({ status: 'error', dependencies: [] })
    }
  }

  const fetchCaptionStyles = async () => {
    try {
      const res = await fetch(`${API_BASE}/clipper/styles`)
      const data = await res.json()
      setCaptionStyles(data)
    } catch (err) {
      console.error('Failed to fetch caption styles:', err)
    }
  }

  const handleUpload = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploading(true)
    setJobResult(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('num_clips', numClips)
    formData.append('min_duration', minDuration)
    formData.append('max_duration', maxDuration)
    formData.append('pause_threshold', pauseThreshold)
    formData.append('caption_style', captionStyle)
    formData.append('whisper_model', whisperModel)
    formData.append('burn_captions', burnCaptions)
    formData.append('crop_vertical', cropVertical)
    formData.append('auto_center', autoCenter)

    try {
      const res = await fetch(`${API_BASE}/clipper/upload`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      
      if (data.job_id) {
        setCurrentJob({ id: data.job_id, status: 'processing', progress: 0, stage: 'Starting' })
        startPolling(data.job_id)
      } else {
        alert('Upload failed: ' + (data.detail || 'Unknown error'))
      }
    } catch (err) {
      console.error('Upload failed:', err)
      alert('Upload failed: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleYoutubeSubmit = async () => {
    if (!youtubeUrl.trim()) return

    setUploading(true)
    setJobResult(null)
    setViralCandidates([])
    setSelectedCandidates(new Set())
    setSmartResults([])
    setClipperPhase('downloading')

    // Everything runs on Railway now
    try {
      const formData = new FormData()
      formData.append('youtube_url', youtubeUrl.trim())
      formData.append('num_clips', numClips)
      formData.append('min_duration', minDuration)
      formData.append('max_duration', maxDuration)
      formData.append('whisper_model', whisperModel)
      formData.append('burn_captions', burnCaptions)
      formData.append('crop_vertical', cropVertical)
      formData.append('auto_center', autoCenter)
      // Style settings
      formData.append('caption_animation', captionAnimation)
      formData.append('caption_color', captionColor)
      formData.append('animation_color', animationColor)
      formData.append('title_style', titleStyle)
      formData.append('title_color', titleColor)
      formData.append('video_vibe', videoVibe)
      formData.append('manual_topic_select', manualTopicSelect)
      formData.append('caption_size', captionSize)
      formData.append('add_stock_images', addStockImages)

      const res = await fetch(`${API_BASE}/clipper/smart/analyze-full`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      
      if (data.job_id) {
        setCurrentJob({ 
          id: data.job_id, 
          status: 'processing', 
          progress: 0, 
          stage: data.cached ? 'Using cached video' : 'Downloading video...',
          cached: data.cached 
        })
        startSmartPolling(data.job_id)
        setYoutubeUrl('')
      } else {
        alert('Failed to start: ' + (data.detail || 'Unknown error'))
        setClipperPhase('input')
      }
    } catch (err) {
      console.error('Processing failed:', err)
      alert('Failed: ' + err.message)
      setClipperPhase('input')
    } finally {
      setUploading(false)
    }
  }
  
  const startSmartPolling = (jobId) => {
    if (pollInterval) clearInterval(pollInterval)
    let notFoundCount = 0
    
    const interval = setInterval(async () => {
      try {
        // Fetch job status
        const res = await fetch(`${API_BASE}/clipper/job/${jobId}`)
        
        // Handle 404 - job not found (server may have restarted)
        if (res.status === 404) {
          notFoundCount++
          console.warn(`Job ${jobId} not found (attempt ${notFoundCount})`)
          
          if (notFoundCount >= 3) {
            clearInterval(interval)
            setPollInterval(null)
            setCurrentJob(prev => ({ 
              ...prev, 
              status: 'failed',
              error: 'Job lost - server may have restarted. Please try again.' 
            }))
            setClipperPhase('input')
            return
          }
          return // Wait and retry
        }
        
        notFoundCount = 0 // Reset on success
        const data = await res.json()
        
        // Also fetch logs
        try {
          const logsRes = await fetch(`${API_BASE}/clipper/job/${jobId}/logs`)
          if (logsRes.ok) {
            const logsData = await logsRes.json()
            setJobLogs(logsData.logs || [])
          }
        } catch (e) {}
        
        setCurrentJob(prev => ({
          ...prev,
          status: data.status,
          progress: data.progress,
          stage: data.stage,
          detail: data.detail,
        }))
        
        // Simple phase management - everything on Railway
        if (data.status === 'processing') {
          setClipperPhase('downloading') // Show progress bar
          
          // Fetch any completed clips progressively (every 5 polls)
          if (Math.random() < 0.2) { // ~20% chance each poll to reduce load
            fetchSmartResults(jobId, false) // Not final
          }
        } else if (data.status === 'completed') {
          clearInterval(interval)
          setPollInterval(null)
          fetchSmartResults(jobId, true) // Final fetch
          localStorage.removeItem('clipper_current_job')
        } else if (data.status === 'failed') {
          clearInterval(interval)
          setPollInterval(null)
          setCurrentJob(prev => ({ ...prev, error: data.error || data.detail }))
          localStorage.removeItem('clipper_current_job')
          setClipperPhase('input')
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 2000)
    
    setPollInterval(interval)
  }
  
  const handleClipEditRequest = async (clip, clipIndex, editRequest) => {
    if (!editRequest.trim()) return
    
    try {
      const formData = new FormData()
      formData.append('job_id', currentJob?.id || '')
      formData.append('clip_index', clipIndex)
      formData.append('edit_request', editRequest)
      formData.append('original_start', clip.start_time)
      formData.append('original_end', clip.end_time)
      // Pass current style settings
      formData.append('caption_color', captionColor)
      formData.append('animation_color', animationColor)
      formData.append('caption_size', captionSize)
      formData.append('video_vibe', videoVibe)
      
      const res = await fetch(`${API_BASE}/clipper/smart/edit-clip`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      
      if (data.success) {
        alert('AI is re-rendering your clip! Check back in a moment.')
        // Clear the edit request
        setClipEditRequests(prev => ({ ...prev, [clipIndex]: '' }))
        // Could trigger a refresh here
      } else {
        alert('Edit request failed: ' + (data.error || 'Unknown error'))
      }
    } catch (err) {
      console.error('Edit request failed:', err)
      alert('Failed to submit edit request')
    }
  }
  
  const handleCancelJob = async () => {
    if (!currentJob?.id) return
    
    try {
      await fetch(`${API_BASE}/clipper/job/${currentJob.id}/cancel`, { method: 'POST' })
      if (pollInterval) {
        clearInterval(pollInterval)
        setPollInterval(null)
      }
      setCurrentJob(null)
      setClipperPhase('input')
      setSmartResults([])
      localStorage.removeItem('clipper_current_job')
    } catch (err) {
      console.error('Cancel failed:', err)
    }
  }
  
  const fetchSmartResults = async (jobId, isFinal = false) => {
    try {
      const res = await fetch(`${API_BASE}/clipper/smart/${jobId}/results`)
      const data = await res.json()
      if (data.clips && data.clips.length > 0) {
        // Update with any new completed clips (progressive loading)
        setSmartResults(data.clips.filter(c => c.ready !== false))
        if (isFinal) {
          setClipperPhase('done')
          // Clear persisted job when done
          localStorage.removeItem('clipper_current_job')
        }
      }
    } catch (err) {
      console.error('Failed to fetch results:', err)
    }
  }
  
  // Persist current job to localStorage for tab switching
  useEffect(() => {
    if (currentJob?.id && currentJob.status === 'processing') {
      localStorage.setItem('clipper_current_job', JSON.stringify({
        id: currentJob.id,
        startedAt: Date.now(),
      }))
    }
  }, [currentJob?.id, currentJob?.status])
  
  // Resume job on page load if one was running
  useEffect(() => {
    const savedJob = localStorage.getItem('clipper_current_job')
    if (savedJob && !currentJob) {
      try {
        const { id, startedAt } = JSON.parse(savedJob)
        // Only resume if less than 30 minutes old
        if (Date.now() - startedAt < 30 * 60 * 1000) {
          console.log('Resuming job:', id)
          setCurrentJob({ id, status: 'resuming', progress: 0, stage: 'Reconnecting...' })
          setClipperPhase('downloading')
          startSmartPolling(id)
        } else {
          localStorage.removeItem('clipper_current_job')
        }
      } catch (e) {
        localStorage.removeItem('clipper_current_job')
      }
    }
  }, [])
  
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${mins}:${secs.toString().padStart(2, '0')}`
  }
  
  const toggleCandidateSelection = (index) => {
    setSelectedCandidates(prev => {
      const newSet = new Set(prev)
      if (newSet.has(index)) {
        newSet.delete(index)
      } else {
        newSet.add(index)
      }
      return newSet
    })
  }
  
  const handleRenderSelected = async (renderOnPC = false) => {
    if (selectedCandidates.size === 0) {
      alert('Please select at least one clip to render')
      return
    }
    
    setClipperPhase('rendering')
    
    try {
      const formData = new FormData()
      formData.append('selected_indices', JSON.stringify([...selectedCandidates]))
      formData.append('burn_captions', burnCaptions)
      formData.append('crop_vertical', cropVertical)
      formData.append('auto_center', autoCenter)
      formData.append('caption_style', captionStyle)
      formData.append('use_local_worker', renderOnPC)  // Explicit choice
      
      const res = await fetch(`${API_BASE}/clipper/smart/${currentJob.id}/render`, {
        method: 'POST',
        body: formData,
      })
      const data = await res.json()
      
      if (data.status === 'queued') {
        // Waiting for local worker
        setCurrentJob(prev => ({
          ...prev,
          status: 'queued',
          stage: 'Waiting for local worker',
          detail: `Ready to render ${data.clips_to_render} clips on your PC`,
        }))
        setClipperPhase('waiting')
        startSmartPolling(currentJob.id)
      } else if (data.status === 'rendering') {
        setCurrentJob(prev => ({
          ...prev,
          status: 'rendering',
          progress: 0,
          stage: 'Rendering on Railway...',
        }))
        startRenderPolling(currentJob.id)
      }
    } catch (err) {
      console.error('Render failed:', err)
      alert('Failed to start rendering: ' + err.message)
      setClipperPhase('select')
    }
  }
  
  const startRenderPolling = (jobId) => {
    if (pollInterval) clearInterval(pollInterval)
    
    const interval = setInterval(async () => {
      try {
        // Fetch job status
        const res = await fetch(`${API_BASE}/clipper/job/${jobId}`)
        const data = await res.json()
        
        // Fetch logs
        try {
          const logsRes = await fetch(`${API_BASE}/clipper/job/${jobId}/logs`)
          const logsData = await logsRes.json()
          setJobLogs(logsData.logs || [])
        } catch (e) {}
        
        setCurrentJob(prev => ({
          ...prev,
          status: data.status,
          progress: data.progress,
          stage: data.stage,
          detail: data.detail,
        }))
        
        if (data.status === 'completed') {
          clearInterval(interval)
          setPollInterval(null)
          // Fetch results
          const resultsRes = await fetch(`${API_BASE}/clipper/smart/${jobId}/results`)
          const resultsData = await resultsRes.json()
          if (resultsData.clips && resultsData.clips.length > 0) {
            setSmartResults(resultsData.clips)
            setClipperPhase('done')
          } else {
            alert('Rendering completed but no clips found. Check logs.')
            setClipperPhase('select')
          }
        } else if (data.status === 'failed') {
          clearInterval(interval)
          setPollInterval(null)
          alert('Rendering failed: ' + (data.error || data.detail || 'Unknown error'))
          setClipperPhase('select')
        }
      } catch (err) {
        console.error('Polling error:', err)
      }
    }, 2000)
    
    setPollInterval(interval)
  }

  const [pollErrorCount, setPollErrorCount] = useState(0)
  const pollErrorCountRef = useRef(0)

  const startPolling = (jobId) => {
    if (pollInterval) clearInterval(pollInterval)
    setPollErrorCount(0)
    pollErrorCountRef.current = 0
    
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/clipper/job/${jobId}`)
        
        // Handle server errors (crash/OOM)
        if (res.status === 502 || res.status === 503 || res.status === 500) {
          pollErrorCountRef.current += 1
          console.log(`Server error ${res.status}, count: ${pollErrorCountRef.current}`)
          
          if (pollErrorCountRef.current >= 3) {
            clearInterval(interval)
            setPollInterval(null)
            setCurrentJob({
              id: jobId,
              status: 'failed',
              progress: 0,
              stage: 'Server Crashed',
              detail: 'Out of memory',
              error: '⚠️ Server ran out of memory while loading Whisper model. Railway free tier has limited RAM (~512MB). Try: 1) Disable "Burn captions" to skip transcription, or 2) Use a local setup instead.'
            })
          }
          return
        }
        
        // Handle job not found (server restarted)
        if (res.status === 404) {
          pollErrorCountRef.current += 1
          console.log(`Job not found, count: ${pollErrorCountRef.current}`)
          
          if (pollErrorCountRef.current >= 2) {
            clearInterval(interval)
            setPollInterval(null)
            setCurrentJob({
              id: jobId,
              status: 'failed',
              progress: 0,
              stage: 'Job Lost',
              detail: 'Server restarted',
              error: '⚠️ Job was lost because the server restarted (likely crashed from low memory). Disable "Burn captions" to skip the memory-heavy transcription step.'
            })
          }
          return
        }
        
        // Success - reset error count
        pollErrorCountRef.current = 0
        const data = await res.json()
        
        setCurrentJob({
          id: jobId,
          status: data.status,
          progress: data.progress,
          stage: data.stage,
          detail: data.detail,
          error: data.error,
        })
        
        if (data.status === 'completed') {
          clearInterval(interval)
          setPollInterval(null)
          fetchJobResult(jobId)
        } else if (data.status === 'failed' || data.status === 'cancelled') {
          clearInterval(interval)
          setPollInterval(null)
        }
      } catch (err) {
        console.error('Polling network error:', err)
        pollErrorCountRef.current += 1
        
        if (pollErrorCountRef.current >= 5) {
          clearInterval(interval)
          setPollInterval(null)
          setCurrentJob({
            id: jobId,
            status: 'failed',
            progress: 0,
            stage: 'Connection Lost',
            detail: 'Network error',
            error: 'Lost connection to server. The server may have crashed or restarted. Please try again.'
          })
        }
      }
    }, 2000) // Poll every 2 seconds
    
    setPollInterval(interval)
  }

  const cancelJob = async () => {
    if (!currentJob?.id) return
    
    try {
      const res = await fetch(`${API_BASE}/clipper/job/${currentJob.id}/cancel`, {
        method: 'POST',
      })
      const data = await res.json()
      
      if (data.cancelled) {
        setCurrentJob(prev => ({
          ...prev,
          status: 'cancelling',
          stage: 'Cancelling...',
          detail: 'Waiting for current operation to complete'
        }))
      }
    } catch (err) {
      console.error('Failed to cancel job:', err)
    }
  }

  const fetchJobResult = async (jobId) => {
    try {
      const res = await fetch(`${API_BASE}/clipper/job/${jobId}/result`)
      const data = await res.json()
      setJobResult(data)
    } catch (err) {
      console.error('Failed to fetch result:', err)
    }
  }

  // Allow usage even if status check fails (server might just be starting)
  const isReady = clipperStatus === null || clipperStatus?.status === 'ready'
  const hasWarnings = clipperStatus && clipperStatus.status !== 'ready' && clipperStatus.dependencies?.some(d => d.status !== 'installed')

  return (
    <section className="clipper-section animate-fade-in">
      <h2 className="section-title">🎬 Video Clipper</h2>
      <p className="section-subtitle">Transform long videos into viral short clips with AI captions</p>

      {/* Status Check - Only show if there are actual missing dependencies */}
      {hasWarnings && (
        <div className="clipper-warning">
          <h3>⚠️ Missing Dependencies</h3>
          <p>Some required tools may not be installed (you can still try):</p>
          <ul>
            {clipperStatus.dependencies?.filter(d => d.status !== 'installed').map((dep, i) => (
              <li key={i}>
                <strong>{dep.name}</strong>
                {dep.instructions && <pre>{dep.instructions}</pre>}
              </li>
            ))}
          </ul>
          <button className="btn btn-secondary btn-sm" onClick={checkClipperStatus} style={{marginTop: '0.5rem'}}>
            🔄 Re-check Status
          </button>
        </div>
      )}

      {/* Settings Panel */}
      <div className="clipper-card">
        <h3>⚙️ Clip Settings</h3>
        
        <div className="clipper-settings-grid">
          <div className="setting-group">
            <label>Number of Clips</label>
            <input 
              type="number" 
              min="1" 
              max="20" 
              value={numClips}
              onChange={(e) => setNumClips(parseInt(e.target.value) || 10)}
            />
          </div>
          
          <div className="setting-group">
            <label>Min Duration (sec)</label>
            <input 
              type="number" 
              min="5" 
              max="120" 
              value={minDuration}
              onChange={(e) => setMinDuration(parseFloat(e.target.value) || 20)}
            />
          </div>
          
          <div className="setting-group">
            <label>Max Duration (sec)</label>
            <input 
              type="number" 
              min="10" 
              max="180" 
              value={maxDuration}
              onChange={(e) => setMaxDuration(parseFloat(e.target.value) || 60)}
            />
          </div>
          
          <div className="setting-group">
            <label>Pause Threshold (sec)</label>
            <input 
              type="number" 
              min="0.3" 
              max="2" 
              step="0.1"
              value={pauseThreshold}
              onChange={(e) => setPauseThreshold(parseFloat(e.target.value) || 0.7)}
            />
          </div>
          
          <div className="setting-group">
            <label>Caption Style</label>
            <select value={captionStyle} onChange={(e) => setCaptionStyle(e.target.value)}>
              {captionStyles.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          
          <div className="setting-group">
            <label>Whisper Model</label>
            <select value={whisperModel} onChange={(e) => setWhisperModel(e.target.value)}>
              <option value="tiny">Tiny (fastest, ~1GB RAM) ⭐</option>
              <option value="base">Base (~1.5GB RAM)</option>
              <option value="small">Small (~2GB RAM)</option>
              <option value="medium">Medium (~5GB RAM)</option>
              <option value="large-v2">Large (~10GB RAM)</option>
            </select>
            <p className="setting-hint">💡 Use Tiny for cloud deployments with limited memory</p>
          </div>
        </div>

        <div className="clipper-options">
          <label className="checkbox-label">
            <input 
              type="checkbox" 
              checked={burnCaptions}
              onChange={(e) => setBurnCaptions(e.target.checked)}
            />
            <span>Burn captions into video</span>
            {!burnCaptions && <span className="option-badge success">Low memory ✓</span>}
          </label>
          <label className="checkbox-label">
            <input 
              type="checkbox" 
              checked={cropVertical}
              onChange={(e) => setCropVertical(e.target.checked)}
            />
            <span>Crop to vertical (9:16)</span>
          </label>
          <label className="checkbox-label">
            <input 
              type="checkbox" 
              checked={autoCenter}
              onChange={(e) => setAutoCenter(e.target.checked)}
            />
            <span>Auto-center on motion</span>
          </label>
          <label className="checkbox-label">
            <input 
              type="checkbox" 
              checked={manualTopicSelect}
              onChange={(e) => setManualTopicSelect(e.target.checked)}
            />
            <span>Let me choose viral topics (shows list to pick from)</span>
          </label>
        </div>
        
        {/* Style Customization Button */}
        <button 
          className="btn btn-secondary style-toggle-btn"
          onClick={() => setShowStylePanel(!showStylePanel)}
        >
          🎨 {showStylePanel ? 'Hide' : 'Customize'} Caption & Title Styles
        </button>
        
        {/* Style Panel */}
        {showStylePanel && (
          <div className="style-panel">
            {/* Video Vibe Selection */}
            <div className="style-section">
              <h4>🎭 Video Vibe</h4>
              <div className="vibe-grid">
                {[
                  { id: 'default', name: 'Default', emoji: '✨', desc: 'Balanced, works for everything' },
                  { id: 'energetic', name: 'Energetic', emoji: '⚡', desc: 'Fast cuts, punchy bass' },
                  { id: 'chill', name: 'Chill', emoji: '😎', desc: 'Relaxed, lo-fi vibes' },
                  { id: 'dramatic', name: 'Dramatic', emoji: '🎬', desc: 'Cinematic, emotional' },
                  { id: 'funny', name: 'Funny', emoji: '😂', desc: 'Quirky, playful' },
                  { id: 'educational', name: 'Educational', emoji: '🧠', desc: 'Clean, professional' },
                ].map(vibe => (
                  <div 
                    key={vibe.id}
                    className={`vibe-card ${videoVibe === vibe.id ? 'selected' : ''}`}
                    onClick={() => setVideoVibe(vibe.id)}
                  >
                    <span className="vibe-emoji">{vibe.emoji}</span>
                    <span className="vibe-name">{vibe.name}</span>
                    <span className="vibe-desc">{vibe.desc}</span>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Caption Animation Selection */}
            <div className="style-section">
              <h4>✍️ Caption Animation</h4>
              <div className="animation-grid">
                {[
                  { id: 'karaoke', name: 'Karaoke', preview: 'word-by-word highlight' },
                  { id: 'pop', name: 'Pop', preview: 'words pop in with scale' },
                  { id: 'typewriter', name: 'Typewriter', preview: 'letters appear one by one' },
                  { id: 'bounce', name: 'Bounce', preview: 'bouncy entrance' },
                  { id: 'fade', name: 'Fade', preview: 'smooth fade in/out' },
                  { id: 'none', name: 'Static', preview: 'no animation' },
                ].map(anim => (
                  <div 
                    key={anim.id}
                    className={`animation-card ${captionAnimation === anim.id ? 'selected' : ''}`}
                    onClick={() => setCaptionAnimation(anim.id)}
                  >
                    <div className={`animation-preview anim-${anim.id}`} style={{ color: captionColor }}>
                      <span style={{ backgroundColor: captionAnimation === anim.id ? animationColor : 'transparent' }}>
                        Sample
                      </span>
                    </div>
                    <span className="animation-name">{anim.name}</span>
                    <span className="animation-desc">{anim.preview}</span>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Caption Colors & Size */}
            <div className="style-section colors-section">
              <h4>🎨 Caption Styling</h4>
              <div className="color-pickers">
                <div className="color-picker-group">
                  <label>Text Color</label>
                  <div className="color-input-row">
                    <input 
                      type="color" 
                      value={captionColor}
                      onChange={(e) => setCaptionColor(e.target.value)}
                    />
                    <div className="color-presets">
                      {['#FFFFFF', '#FFFF00', '#00FF00', '#00FFFF', '#FF00FF', '#FF6600'].map(c => (
                        <button 
                          key={c}
                          className={`color-preset ${captionColor === c ? 'selected' : ''}`}
                          style={{ backgroundColor: c }}
                          onClick={() => setCaptionColor(c)}
                        />
                      ))}
                    </div>
                  </div>
                </div>
                <div className="color-picker-group">
                  <label>Highlight Color (animation)</label>
                  <div className="color-input-row">
                    <input 
                      type="color" 
                      value={animationColor}
                      onChange={(e) => setAnimationColor(e.target.value)}
                    />
                    <div className="color-presets">
                      {['#FFFF00', '#00FF00', '#FF00FF', '#00FFFF', '#FF6600', '#FF0000'].map(c => (
                        <button 
                          key={c}
                          className={`color-preset ${animationColor === c ? 'selected' : ''}`}
                          style={{ backgroundColor: c }}
                          onClick={() => setAnimationColor(c)}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              
              {/* Caption Size Slider */}
              <div className="caption-size-control">
                <label>Caption Size: <strong>{captionSize}px</strong></label>
                <input 
                  type="range"
                  min="50"
                  max="120"
                  value={captionSize}
                  onChange={(e) => setCaptionSize(parseInt(e.target.value))}
                  className="size-slider"
                />
                <div className="size-presets">
                  <button onClick={() => setCaptionSize(60)} className={captionSize === 60 ? 'active' : ''}>S</button>
                  <button onClick={() => setCaptionSize(80)} className={captionSize === 80 ? 'active' : ''}>M</button>
                  <button onClick={() => setCaptionSize(100)} className={captionSize === 100 ? 'active' : ''}>L</button>
                  <button onClick={() => setCaptionSize(120)} className={captionSize === 120 ? 'active' : ''}>XL</button>
                </div>
              </div>
              
              {/* Stock Images Toggle */}
              <div className="stock-images-toggle">
                <label className="checkbox-label">
                  <input 
                    type="checkbox" 
                    checked={addStockImages}
                    onChange={(e) => setAddStockImages(e.target.checked)}
                  />
                  <span>🖼️ Add relevant stock images (Unsplash)</span>
                </label>
                {addStockImages && (
                  <p className="toggle-hint">Images appear above captions for ~2 seconds during key moments</p>
                )}
              </div>
              
              {/* Live 9:16 Preview */}
              <div className="caption-live-preview">
                <h5>📱 Live Preview (9:16)</h5>
                <div className="phone-mockup-916">
                  <div className="phone-notch"></div>
                  <div className="phone-screen-916">
                    {/* Title at top */}
                    <div 
                      className="preview-title"
                      style={{ color: titleColor }}
                    >
                      HOOK TITLE HERE
                    </div>
                    
                    {/* Stock image placeholder */}
                    {addStockImages && (
                      <div className="preview-stock-image">
                        <span>📷 Stock Image</span>
                      </div>
                    )}
                    
                    {/* Caption in middle-lower */}
                    <div 
                      className={`preview-caption-916 anim-${captionAnimation}`}
                      style={{ 
                        color: captionColor,
                        fontSize: `${captionSize * 0.25}px`
                      }}
                    >
                      <span className="highlight-word" style={{ backgroundColor: animationColor + '80' }}>This</span> is how your <span className="highlight-word" style={{ backgroundColor: animationColor + '80' }}>captions</span> look
                    </div>
                    
                    {/* Zoom indicator */}
                    <div className="preview-zoom-indicator">
                      <span>↔️ Zoom every 1.5s</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Title/Header Style Selection */}
            <div className="style-section">
              <h4>📌 Hook Title Style</h4>
              <p className="style-hint">Shown at the top for the first 3-4 seconds</p>
              <div className="title-grid">
                {[
                  { id: 'bold', name: 'Bold', style: { fontWeight: 800, textTransform: 'uppercase' } },
                  { id: 'outline', name: 'Outline', style: { fontWeight: 700, WebkitTextStroke: '2px', WebkitTextFillColor: 'transparent' } },
                  { id: 'shadow', name: 'Shadow', style: { fontWeight: 700, textShadow: '4px 4px 0 #000' } },
                  { id: 'glow', name: 'Glow', style: { fontWeight: 700, textShadow: '0 0 20px currentColor' } },
                  { id: 'minimal', name: 'Minimal', style: { fontWeight: 500, letterSpacing: '0.1em' } },
                  { id: 'retro', name: 'Retro', style: { fontWeight: 800, fontStyle: 'italic', transform: 'skewX(-5deg)' } },
                ].map(title => (
                  <div 
                    key={title.id}
                    className={`title-card ${titleStyle === title.id ? 'selected' : ''}`}
                    onClick={() => setTitleStyle(title.id)}
                  >
                    <div 
                      className="title-preview"
                      style={{ ...title.style, color: titleColor, borderColor: titleColor }}
                    >
                      HOOK TEXT
                    </div>
                    <span className="title-name">{title.name}</span>
                  </div>
                ))}
              </div>
              
              <div className="color-picker-group" style={{ marginTop: '1rem' }}>
                <label>Title Color</label>
                <div className="color-input-row">
                  <input 
                    type="color" 
                    value={titleColor}
                    onChange={(e) => setTitleColor(e.target.value)}
                  />
                  <div className="color-presets">
                    {['#FFFF00', '#FF0000', '#00FF00', '#FFFFFF', '#FF6600', '#00FFFF'].map(c => (
                      <button 
                        key={c}
                        className={`color-preset ${titleColor === c ? 'selected' : ''}`}
                        style={{ backgroundColor: c }}
                        onClick={() => setTitleColor(c)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
        
        {burnCaptions && (
          <p className="memory-warning">
            ⚠️ Captions require loading Whisper AI model (~1GB RAM). If you're on Railway free tier, this may crash. Disable captions to skip transcription.
          </p>
        )}
      </div>

      {/* Railway Cloud Processing Info */}
      <div className="clipper-card railway-info-card">
        <p>☁️ <strong>Powered by Railway</strong> — fast cloud processing with no setup needed. Your clips will be ready in minutes!</p>
      </div>

      {/* Input Section */}
      <div className="clipper-card upload-card">
        <h3>📥 Video Source</h3>
        
        {/* Input Mode Tabs */}
        <div className="input-mode-tabs">
          <button 
            className={`mode-tab ${inputMode === 'upload' ? 'active' : ''}`}
            onClick={() => setInputMode('upload')}
          >
            📤 Upload File
          </button>
          <button 
            className={`mode-tab ${inputMode === 'youtube' ? 'active' : ''}`}
            onClick={() => setInputMode('youtube')}
          >
            ▶️ YouTube URL
          </button>
        </div>

        {inputMode === 'upload' && (
          <>
            <p>Supported formats: MP4, MOV, AVI, MKV, WebM</p>
            <label className="upload-zone">
              <input 
                type="file" 
                accept="video/*"
                onChange={handleUpload}
                disabled={uploading}
              />
              <div className="upload-content">
                <span className="upload-icon">🎥</span>
                <span className="upload-text">
                  {uploading ? 'Uploading...' : 'Click or drag to upload video'}
                </span>
              </div>
            </label>
          </>
        )}

        {inputMode === 'youtube' && (
          <>
            <p>Paste a YouTube video URL to download and process</p>
            <div className="youtube-input-group">
              <input 
                type="text"
                className="youtube-url-input"
                placeholder="https://www.youtube.com/watch?v=... or https://youtu.be/..."
                value={youtubeUrl}
                onChange={(e) => setYoutubeUrl(e.target.value)}
                disabled={uploading}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && youtubeUrl.trim() && !uploading) {
                    handleYoutubeSubmit()
                  }
                }}
              />
              <button 
                className="btn btn-primary"
                onClick={handleYoutubeSubmit}
                disabled={uploading || !youtubeUrl.trim()}
              >
                {uploading ? 'Processing...' : '🚀 Process'}
              </button>
            </div>
            <p className="youtube-hint">
              Supports: youtube.com/watch, youtu.be, youtube.com/shorts
            </p>
          </>
        )}
      </div>

      {/* Processing Progress - Everything on Railway */}
      {clipperPhase === 'downloading' && currentJob && (
        <div className="clipper-card progress-card">
          <div className="progress-header">
            <h3>☁️ Processing on Railway</h3>
            <div className="progress-actions">
              <button 
                className="btn btn-sm btn-secondary"
                onClick={() => setShowLogs(!showLogs)}
              >
                {showLogs ? '📋 Hide Logs' : '📋 Show Logs'}
              </button>
              <button 
                className="btn btn-sm btn-danger"
                onClick={handleCancelJob}
              >
                Cancel
              </button>
            </div>
          </div>
          <div className="progress-bar-container">
            <div 
              className="progress-bar-fill"
              style={{ width: `${(currentJob.progress || 0) * 100}%` }}
            />
          </div>
          <div className="progress-info">
            <p className="progress-text">
              <strong>{Math.round((currentJob.progress || 0) * 100)}%</strong> — {currentJob.stage || 'Starting...'}
            </p>
            {currentJob.detail && (
              <p className="progress-detail">{currentJob.detail}</p>
            )}
          </div>
          
          <p className="progress-hint">
            ☁️ You can switch tabs - processing continues in background!
          </p>
          
          {/* Show completed clips while processing */}
          {smartResults.length > 0 && (
            <div className="early-results">
              <h4>✅ Clips Ready ({smartResults.length})</h4>
              <div className="early-clips-grid">
                {smartResults.map((clip, i) => (
                  <div key={i} className="early-clip">
                    <video 
                      src={`${API_BASE}${clip.video_url}`} 
                      controls 
                      preload="metadata"
                    />
                    <div className="early-clip-info">
                      <span className="score">🔥 {clip.virality_score}</span>
                      <a 
                        href={`${API_BASE}${clip.video_url}`}
                        download
                        className="btn btn-sm btn-primary"
                      >
                        ⬇️
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {showLogs && jobLogs.length > 0 && (
            <div className="job-logs">
              <h4>📋 Live Logs</h4>
              <div className="logs-container">
                {jobLogs.slice(-20).map((log, i) => (
                  <div key={i} className={`log-entry log-${log.level}`}>
                    <span className="log-time">{new Date(log.time).toLocaleTimeString()}</span>
                    <span className="log-message">{log.message}</span>
                    {log.eta && <span className="log-eta">({log.eta})</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Waiting for Worker - now handled inline in downloading phase */}

      {/* Processing on Worker */}
      {clipperPhase === 'analyzing' && currentJob && (
        <div className="clipper-card progress-card">
          <div className="progress-header">
            <h3>🧠 Processing on Your PC</h3>
            <button 
              className="btn btn-sm btn-secondary"
              onClick={() => setShowLogs(!showLogs)}
            >
              {showLogs ? '📋 Hide Logs' : '📋 Show Logs'}
            </button>
          </div>
          <div className="progress-bar-container">
            <div 
              className="progress-bar-fill"
              style={{ width: `${(currentJob.progress || 0) * 100}%` }}
            />
          </div>
          <div className="progress-info">
            <p className="progress-text">
              <strong>{Math.round((currentJob.progress || 0) * 100)}%</strong> — {currentJob.stage || 'Processing...'}
            </p>
            {currentJob.detail && (
              <p className="progress-detail">{currentJob.detail}</p>
            )}
          </div>
          
          <p className="progress-hint">
            💻 Running Whisper transcription and viral analysis on your PC
          </p>
          
          {showLogs && jobLogs.length > 0 && (
            <div className="job-logs">
              <h4>📋 Logs</h4>
              <div className="logs-container">
                {jobLogs.map((log, i) => (
                  <div key={i} className={`log-entry log-${log.level}`}>
                    <span className="log-time">{new Date(log.time).toLocaleTimeString()}</span>
                    <span className="log-message">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Viral Candidates Selection */}
      {clipperPhase === 'select' && viralCandidates.length > 0 && (
        <div className="clipper-card candidates-card">
          <div className="candidates-header">
            <h3>🔥 Viral Moments Found ({viralCandidates.length})</h3>
            <p>Select which clips to render. AI pre-selected the top {numClips} most viral.</p>
          </div>
          
          <div className="candidates-actions">
            <span className="selected-count">{selectedCandidates.size} selected</span>
            <div className="render-buttons">
              <button 
                className="btn btn-primary"
                onClick={() => handleRenderSelected(false)}
                disabled={selectedCandidates.size === 0}
              >
                ☁️ Render on Railway
              </button>
              <button 
                className="btn btn-secondary"
                onClick={() => handleRenderSelected(true)}
                disabled={selectedCandidates.size === 0}
              >
                🖥️ Render on My PC
              </button>
            </div>
          </div>
          
          <div className="candidates-list">
            {viralCandidates.map((candidate, idx) => (
              <div 
                key={idx}
                className={`candidate-card ${selectedCandidates.has(candidate.index) ? 'selected' : ''}`}
                onClick={() => toggleCandidateSelection(candidate.index)}
              >
                <div className="candidate-header">
                  <div className="candidate-select">
                    <input 
                      type="checkbox"
                      checked={selectedCandidates.has(candidate.index)}
                      onChange={() => toggleCandidateSelection(candidate.index)}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </div>
                  <div className="candidate-score">
                    <span className="score-badge" style={{
                      background: candidate.virality_score >= 80 ? '#00c864' : 
                                  candidate.virality_score >= 60 ? '#ffaa00' : '#ff6464'
                    }}>
                      {candidate.virality_score}
                    </span>
                    <span className="category-badge">{candidate.category}</span>
                  </div>
                  <div className="candidate-time">
                    {candidate.duration.toFixed(0)}s ({formatTime(candidate.start_time)} - {formatTime(candidate.end_time)})
                  </div>
                </div>
                
                <div className="candidate-content">
                  <p className="candidate-text">"{candidate.text.slice(0, 200)}{candidate.text.length > 200 ? '...' : ''}"</p>
                  
                  <div className="candidate-virality">
                    <strong>🔥 Why it's viral:</strong> {candidate.virality_reason}
                  </div>
                  
                  <div className="candidate-suggestions">
                    <div className="suggestion-item">
                      <strong>📝 Caption:</strong> {candidate.suggested_caption}
                    </div>
                    <div className="suggestion-item">
                      <strong>#️⃣ Hashtags:</strong> {candidate.suggested_hashtags.map(h => `#${h}`).join(' ')}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rendering Progress */}
      {clipperPhase === 'rendering' && currentJob && (
        <div className="clipper-card progress-card">
          <div className="progress-header">
            <h3>🎬 Rendering Selected Clips</h3>
            <button 
              className="btn btn-sm btn-secondary"
              onClick={() => setShowLogs(!showLogs)}
            >
              {showLogs ? '📋 Hide Logs' : '📋 Show Logs'}
            </button>
          </div>
          <div className="progress-bar-container">
            <div 
              className="progress-bar-fill"
              style={{ width: `${(currentJob.progress || 0) * 100}%` }}
            />
          </div>
          <div className="progress-info">
            <p className="progress-text">
              <strong>{Math.round((currentJob.progress || 0) * 100)}%</strong> — {currentJob.stage || 'Starting render...'}
            </p>
            {currentJob.detail && (
              <p className="progress-detail">{currentJob.detail}</p>
            )}
          </div>
          
          <p className="progress-hint">
            ⏳ This may take a few minutes. Each clip takes ~30s to render.
          </p>
          
          {showLogs && jobLogs.length > 0 && (
            <div className="job-logs">
              <h4>📋 Logs</h4>
              <div className="logs-container">
                {jobLogs.map((log, i) => (
                  <div key={i} className={`log-entry log-${log.level}`}>
                    <span className="log-time">{new Date(log.time).toLocaleTimeString()}</span>
                    <span className="log-message">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Smart Results */}
      {clipperPhase === 'done' && smartResults.length > 0 && (
        <div className="clipper-card results-card">
          <h3>✅ Your Viral Clips Are Ready!</h3>
          <div className="results-summary">
            <span>Rendered {smartResults.length} clips</span>
            <button 
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setClipperPhase('input')
                setViralCandidates([])
                setSmartResults([])
                setCurrentJob(null)
              }}
            >
              Create More Clips
            </button>
          </div>

          <div className="clips-grid">
            {smartResults.map((clip, idx) => (
              <div key={idx} className="clip-card smart-clip">
                <div className="clip-preview">
                  <video 
                    src={clip.video_url} 
                    controls 
                    preload="metadata"
                  />
                </div>
                <div className="clip-info">
                  <div className="clip-header">
                    <span className="clip-number">Clip {clip.index}</span>
                    <span className="virality-score" style={{
                      background: clip.virality_score >= 80 ? '#00c864' : 
                                  clip.virality_score >= 60 ? '#ffaa00' : '#ff6464'
                    }}>
                      🔥 {clip.virality_score}
                    </span>
                  </div>
                  
                  <div className="clip-virality-reason">
                    <strong>Why it's viral:</strong> {clip.virality_reason}
                  </div>
                  
                  <div className="clip-copy-section">
                    <div className="copy-item">
                      <label>Caption:</label>
                      <div className="copy-content">
                        <span>{clip.suggested_caption}</span>
                        <button 
                          className="btn-copy"
                          onClick={() => {
                            navigator.clipboard.writeText(clip.suggested_caption)
                            alert('Caption copied!')
                          }}
                        >
                          📋
                        </button>
                      </div>
                    </div>
                    
                    <div className="copy-item">
                      <label>Hashtags:</label>
                      <div className="copy-content">
                        <span>{clip.suggested_hashtags.map(h => `#${h}`).join(' ')}</span>
                        <button 
                          className="btn-copy"
                          onClick={() => {
                            navigator.clipboard.writeText(clip.suggested_hashtags.map(h => `#${h}`).join(' '))
                            alert('Hashtags copied!')
                          }}
                        >
                          📋
                        </button>
                      </div>
                    </div>
                  </div>
                  
                  <a 
                    href={clip.video_url} 
                    download={`clip_${clip.index}.mp4`}
                    className="btn btn-primary btn-sm"
                    style={{marginTop: '0.5rem', display: 'block', textAlign: 'center'}}
                  >
                    ⬇️ Download
                  </a>
                  
                  {/* AI Edit Request Box */}
                  <div className="clip-edit-request">
                    <label>🤖 Request AI Edit:</label>
                    <textarea 
                      placeholder="e.g. 'Make it funnier', 'Add more zoom', 'Change music to dramatic'..."
                      value={clipEditRequests[idx] || ''}
                      onChange={(e) => setClipEditRequests(prev => ({
                        ...prev,
                        [idx]: e.target.value
                      }))}
                      rows={2}
                    />
                    {clipEditRequests[idx] && (
                      <button 
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleClipEditRequest(clip, idx, clipEditRequests[idx])}
                      >
                        ✨ Re-render with AI
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Legacy Progress (for old flow) */}
      {currentJob && ['processing', 'cancelling'].includes(currentJob.status) && clipperPhase === 'input' && (
        <div className="clipper-card progress-card">
          <div className="progress-header">
            <h3>{currentJob.status === 'cancelling' ? '⏳ Cancelling...' : '🔄 Processing'}</h3>
            {currentJob.status === 'processing' && (
              <button 
                className="btn btn-danger btn-sm"
                onClick={cancelJob}
              >
                ✕ Cancel
              </button>
            )}
          </div>
          <div className="progress-bar-container">
            <div 
              className="progress-bar-fill"
              style={{ width: `${currentJob.progress * 100}%` }}
            />
          </div>
          <div className="progress-info">
            <p className="progress-text">
              <strong>{Math.round(currentJob.progress * 100)}%</strong> — {currentJob.stage}
            </p>
            {currentJob.detail && (
              <p className="progress-detail">{currentJob.detail}</p>
            )}
          </div>
          <p className="progress-hint">
            💡 You can close this page - processing will continue in the background. 
            Check back later using the job ID: <code>{currentJob.id}</code>
          </p>
        </div>
      )}

      {/* Cancelled */}
      {currentJob && currentJob.status === 'cancelled' && (
        <div className="clipper-card warning-card">
          <h3>⏹️ Job Cancelled</h3>
          <p>{currentJob.detail || 'The job was cancelled by user request.'}</p>
          <button 
            className="btn btn-primary btn-sm"
            onClick={() => setCurrentJob(null)}
          >
            Start New Job
          </button>
        </div>
      )}

      {/* Error */}
      {currentJob && currentJob.status === 'failed' && (
        <div className="clipper-card error-card">
          <h3>❌ Processing Failed</h3>
          <p className="error-message">{currentJob.error || 'Unknown error occurred'}</p>
          {currentJob.detail && (
            <p className="error-detail">Stage: {currentJob.stage} - {currentJob.detail}</p>
          )}
          <button 
            className="btn btn-primary btn-sm"
            onClick={() => setCurrentJob(null)}
            style={{marginTop: '1rem'}}
          >
            Try Again
          </button>
        </div>
      )}

      {/* Results */}
      {jobResult && jobResult.success && (
        <div className="clipper-card results-card">
          <h3>✅ Clips Ready!</h3>
          <div className="results-summary">
            <span>Generated {jobResult.clips.length} clips</span>
            <span>•</span>
            <span>Processing time: {jobResult.processing_time.toFixed(1)}s</span>
          </div>

          <div className="clips-grid">
            {jobResult.clips.map((clip, idx) => (
              <div key={idx} className="clip-card">
                <div className="clip-preview">
                  <video 
                    src={clip.video_url} 
                    controls 
                    preload="metadata"
                  />
                </div>
                <div className="clip-info">
                  <div className="clip-header">
                    <span className="clip-number">Clip {clip.index}</span>
                    <span className="clip-score">Score: {clip.score.toFixed(2)}</span>
                  </div>
                  <div className="clip-meta">
                    <span>{clip.duration.toFixed(1)}s</span>
                    <span>•</span>
                    <span>{clip.start_time.toFixed(1)}s - {clip.end_time.toFixed(1)}s</span>
                  </div>
                  <p className="clip-text">{clip.text.slice(0, 100)}...</p>
                  <a 
                    href={clip.video_url} 
                    download={`clip_${clip.index}.mp4`}
                    className="btn btn-primary btn-sm"
                  >
                    📥 Download
                  </a>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

function AutoPostPage({
  settings,
  scheduledPosts,
  contentTemplates,
  colorThemes,
  textures,
  layouts,
  onSaveSettings,
  onGenerateQueue,
  onDeleteScheduled,
  onSchedulePost,
  savingSettings
}) {
  const [localSettings, setLocalSettings] = useState(settings || {
    enabled: false,
    posts_per_day: 3,
    carousel_count: 2,
    news_count: 1,
    equal_distribution: true,
    default_template_id: null,
    default_color_theme: null,
    default_texture: null,
    default_layout: null,
    default_slide_count: 4,
    news_accent_color: 'cyan',
    news_time_range: '1d',
    news_auto_select: true,
    instagram_username: '',
  })
  const [newPostSettings, setNewPostSettings] = useState({
    useDefault: true,
    post_type: 'carousel',
    template_id: null,
    color_theme: null,
    texture: null,
    layout: null,
    slide_count: 4,
  })
  const [igConnection, setIgConnection] = useState(null)
  const [checkingConnection, setCheckingConnection] = useState(false)

  useEffect(() => {
    if (settings) {
      setLocalSettings({
        ...localSettings,
        ...settings,
        carousel_count: settings.carousel_count ?? 2,
        news_count: settings.news_count ?? 1,
        equal_distribution: settings.equal_distribution ?? true,
        news_accent_color: settings.news_accent_color ?? 'cyan',
        news_time_range: settings.news_time_range ?? '1d',
        news_auto_select: settings.news_auto_select ?? true,
      })
    }
    checkInstagramConnection()
  }, [settings])

  const checkInstagramConnection = async () => {
    setCheckingConnection(true)
    try {
      const res = await fetch(`${API_BASE}/instagram/verify`)
      const data = await res.json()
      setIgConnection(data)
    } catch (err) {
      setIgConnection({ status: 'error', error: 'Failed to check connection' })
    } finally {
      setCheckingConnection(false)
    }
  }

  const handleSave = () => {
    onSaveSettings(localSettings)
  }

  const handleScheduleNew = () => {
    const options = newPostSettings.useDefault
      ? { slide_count: 4 }
      : {
          template_id: newPostSettings.template_id,
          color_theme: newPostSettings.color_theme,
          texture: newPostSettings.texture,
          layout: newPostSettings.layout,
          slide_count: newPostSettings.slide_count,
        }
    onSchedulePost(options)
  }

  const formatTime = (isoString) => {
    const date = new Date(isoString)
    return date.toLocaleString()
  }

  return (
    <section className="autopost-section animate-fade-in">
      <h2 className="section-title">Auto Posting</h2>

      {/* Instagram Connection Status */}
      <div className="autopost-card ig-connection-card">
        <div className="autopost-header">
          <h3>📸 Instagram Connection</h3>
          <button 
            className="btn btn-secondary btn-sm"
            onClick={checkInstagramConnection}
            disabled={checkingConnection}
          >
            {checkingConnection ? 'Checking...' : 'Refresh'}
          </button>
        </div>
        {igConnection ? (
          igConnection.status === 'valid' ? (
            <div className="ig-connected">
              <div className="ig-status success">✓ Connected</div>
              <div className="ig-details">
                <span className="ig-username">@{igConnection.username}</span>
                <span className="ig-type">{igConnection.account_type}</span>
                <span className="ig-posts">{igConnection.media_count} posts</span>
              </div>
            </div>
          ) : (
            <div className="ig-disconnected">
              <div className="ig-status error">✗ Not Connected</div>
              <p className="ig-error">{igConnection.error || 'Unable to verify connection'}</p>
            </div>
          )
        ) : (
          <p className="ig-loading">Checking connection...</p>
        )}
      </div>

      {/* Main Toggle */}
      <div className="autopost-card">
        <div className="autopost-header">
          <h3>Auto-Posting Status</h3>
          <label className="toggle-switch">
            <input
              type="checkbox"
              checked={localSettings.enabled}
              onChange={(e) => setLocalSettings({ ...localSettings, enabled: e.target.checked })}
            />
            <span className="toggle-slider"></span>
          </label>
        </div>
        <p className="autopost-status">
          {localSettings.enabled ? '✅ Auto-posting is enabled' : '⏸️ Auto-posting is paused'}
        </p>
      </div>

      {/* Post Type Distribution */}
      <div className="autopost-card">
        <h3>📊 Post Distribution</h3>
        <p className="form-hint">Choose how many of each post type to publish daily</p>
        
        <div className="distribution-grid">
          <div className="distribution-item">
            <label className="form-label">📸 Carousels per day</label>
            <div className="count-input-row">
              <input
                type="number"
                className="form-input count-input"
                min="0"
                max="20"
                value={localSettings.carousel_count}
                onChange={(e) => {
                  const val = Math.max(0, Math.min(20, parseInt(e.target.value) || 0))
                  setLocalSettings({ ...localSettings, carousel_count: val, posts_per_day: val + localSettings.news_count })
                }}
              />
              <div className="quick-btns">
                {[0, 1, 2, 3, 5, 10].map((num) => (
                  <button
                    key={num}
                    className={`quick-btn ${localSettings.carousel_count === num ? 'selected' : ''}`}
                    onClick={() => setLocalSettings({ ...localSettings, carousel_count: num, posts_per_day: num + localSettings.news_count })}
                  >
                    {num}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="distribution-item">
            <label className="form-label">📰 News Posts per day</label>
            <div className="count-input-row">
              <input
                type="number"
                className="form-input count-input"
                min="0"
                max="20"
                value={localSettings.news_count}
                onChange={(e) => {
                  const val = Math.max(0, Math.min(20, parseInt(e.target.value) || 0))
                  setLocalSettings({ ...localSettings, news_count: val, posts_per_day: localSettings.carousel_count + val })
                }}
              />
              <div className="quick-btns">
                {[0, 1, 2, 3, 5, 10].map((num) => (
                  <button
                    key={num}
                    className={`quick-btn ${localSettings.news_count === num ? 'selected' : ''}`}
                    onClick={() => setLocalSettings({ ...localSettings, news_count: num, posts_per_day: localSettings.carousel_count + num })}
                  >
                    {num}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="total-posts">
          <strong>Total: {(localSettings.carousel_count || 0) + (localSettings.news_count || 0)} posts/day</strong>
          <span className="hint">
            ({(24 / Math.max((localSettings.carousel_count || 0) + (localSettings.news_count || 0), 1)).toFixed(1)} hours apart)
          </span>
        </div>

        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={localSettings.equal_distribution}
            onChange={(e) => setLocalSettings({ ...localSettings, equal_distribution: e.target.checked })}
          />
          <span>Distribute equally throughout the day (mix post types)</span>
        </label>
      </div>

      {/* Carousel Default Settings */}
      <div className="autopost-card">
        <h3>📸 Carousel Defaults</h3>
        <p className="form-hint">Leave as "Random" to randomize each carousel's style</p>
        
        <div className="default-settings-grid">
          <div className="setting-row">
            <label className="form-label">Content Template</label>
            <select
              className="form-select"
              value={localSettings.default_template_id || ''}
              onChange={(e) => setLocalSettings({ ...localSettings, default_template_id: e.target.value || null })}
            >
              <option value="">Random</option>
              {contentTemplates.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          <div className="setting-row">
            <label className="form-label">Color Theme</label>
            <select
              className="form-select"
              value={localSettings.default_color_theme || ''}
              onChange={(e) => setLocalSettings({ ...localSettings, default_color_theme: e.target.value || null })}
            >
              <option value="">Random</option>
              {colorThemes.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          <div className="setting-row">
            <label className="form-label">Background Texture</label>
            <select
              className="form-select"
              value={localSettings.default_texture || ''}
              onChange={(e) => setLocalSettings({ ...localSettings, default_texture: e.target.value || null })}
            >
              <option value="">Random</option>
              {textures.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          <div className="setting-row">
            <label className="form-label">Layout Style</label>
            <select
              className="form-select"
              value={localSettings.default_layout || ''}
              onChange={(e) => setLocalSettings({ ...localSettings, default_layout: e.target.value || null })}
            >
              <option value="">Random</option>
              {layouts.map((l) => (
                <option key={l.id} value={l.id}>{l.name}</option>
              ))}
            </select>
          </div>

          <div className="setting-row">
            <label className="form-label">Slide Count</label>
            <select
              className="form-select"
              value={localSettings.default_slide_count || 0}
              onChange={(e) => setLocalSettings({ ...localSettings, default_slide_count: parseInt(e.target.value) || null })}
            >
              <option value="0">Random (4-10)</option>
              {[4, 5, 6, 7, 8, 9, 10].map((n) => (
                <option key={n} value={n}>{n} slides</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* News Post Default Settings */}
      <div className="autopost-card">
        <h3>📰 News Post Defaults</h3>
        <p className="form-hint">Settings for auto-generated news posts</p>
        
        <div className="default-settings-grid">
          <div className="setting-row">
            <label className="form-label">Highlight Color</label>
            <div className="color-picker-row">
              <button
                className={`color-btn random-color ${localSettings.news_accent_color === 'random' ? 'selected' : ''}`}
                onClick={() => setLocalSettings({ ...localSettings, news_accent_color: 'random' })}
                title="Random"
              >
                🎲
              </button>
              {['cyan', 'blue', 'green', 'orange', 'red', 'yellow', 'pink', 'purple'].map(color => (
                <button
                  key={color}
                  className={`color-btn ${localSettings.news_accent_color === color ? 'selected' : ''}`}
                  style={{ backgroundColor: color }}
                  onClick={() => setLocalSettings({ ...localSettings, news_accent_color: color })}
                  title={color}
                />
              ))}
            </div>
          </div>

          <div className="setting-row">
            <label className="form-label">News Time Range</label>
            <select
              className="form-select"
              value={localSettings.news_time_range || '1d'}
              onChange={(e) => setLocalSettings({ ...localSettings, news_time_range: e.target.value })}
            >
              <option value="today">Today</option>
              <option value="1d">Past 24 Hours</option>
              <option value="3d">Past 3 Days</option>
              <option value="1w">Past Week</option>
              <option value="2w">Past 2 Weeks</option>
              <option value="4w">Past Month</option>
            </select>
          </div>

          <div className="setting-row full-width">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={localSettings.news_auto_select}
                onChange={(e) => setLocalSettings({ ...localSettings, news_auto_select: e.target.checked })}
              />
              <span>AI auto-selects most viral topic</span>
            </label>
          </div>
        </div>
      </div>

      {/* Instagram Credentials */}
      <div className="autopost-card">
        <h3>Instagram Credentials</h3>
        <p className="form-hint">Required for automatic posting</p>
        
        <div className="credentials-form">
          <div className="form-group">
            <label className="form-label">Username</label>
            <input
              type="text"
              className="form-input"
              placeholder="@username"
              value={localSettings.instagram_username || ''}
              onChange={(e) => setLocalSettings({ ...localSettings, instagram_username: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Password</label>
            <input
              type="password"
              className="form-input"
              placeholder="••••••••"
              onChange={(e) => setLocalSettings({ ...localSettings, instagram_password: e.target.value })}
            />
            {settings?.has_credentials && (
              <p className="form-hint success">✓ Credentials saved</p>
            )}
          </div>
        </div>
      </div>

      {/* Save Button */}
      <button
        className="btn btn-primary btn-lg save-settings-btn"
        onClick={handleSave}
        disabled={savingSettings}
      >
        {savingSettings ? 'Saving...' : 'Save Settings'}
      </button>

      {/* Scheduled Posts Queue */}
      <div className="autopost-card scheduled-queue">
        <div className="queue-header">
          <h3>Scheduled Posts</h3>
          <button className="btn btn-secondary" onClick={onGenerateQueue}>
            Generate Daily Queue
          </button>
        </div>

        {/* Schedule New Post */}
        <div className="schedule-new">
          <h4>Schedule a Post</h4>
          <div className="schedule-options">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={newPostSettings.useDefault}
                onChange={(e) => setNewPostSettings({ ...newPostSettings, useDefault: e.target.checked })}
              />
              <span>Use default settings (or random)</span>
            </label>
            
            {!newPostSettings.useDefault && (
              <div className="custom-schedule-settings">
                <select
                  className="form-select"
                  value={newPostSettings.template_id || ''}
                  onChange={(e) => setNewPostSettings({ ...newPostSettings, template_id: e.target.value || null })}
                >
                  <option value="">Random Template</option>
                  {contentTemplates.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
                <select
                  className="form-select"
                  value={newPostSettings.color_theme || ''}
                  onChange={(e) => setNewPostSettings({ ...newPostSettings, color_theme: e.target.value || null })}
                >
                  <option value="">Random Color</option>
                  {colorThemes.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>
              </div>
            )}
            
            <button className="btn btn-primary" onClick={handleScheduleNew}>
              + Schedule Post
            </button>
          </div>
        </div>

        {/* Queue List */}
        {scheduledPosts.length === 0 ? (
          <div className="empty-queue">
            <p>No posts scheduled. Click "Generate Daily Queue" to create today's schedule.</p>
          </div>
        ) : (
          <div className="queue-list">
            {scheduledPosts.map((post) => (
              <div key={post.id} className={`queue-item status-${post.status} type-${post.post_type || 'carousel'}`}>
                <div className="queue-item-time">
                  <span className="queue-time">{formatTime(post.scheduled_time)}</span>
                  <span className={`queue-status ${post.status}`}>{post.status}</span>
                </div>
                <div className="queue-item-type">
                  <span className={`type-badge ${post.post_type || 'carousel'}`}>
                    {(post.post_type || 'carousel') === 'news' ? '📰 News' : '📸 Carousel'}
                  </span>
                </div>
                <div className="queue-item-details">
                  {(post.post_type || 'carousel') === 'carousel' ? (
                    <>
                      <span>{post.template_id || 'Random'}</span>
                      <span>•</span>
                      <span>{post.color_theme || 'Random'}</span>
                      <span>•</span>
                      <span>{post.slide_count || 4} slides</span>
                    </>
                  ) : (
                    <>
                      <span style={{ color: post.news_accent_color || 'cyan' }}>●</span>
                      <span>{post.news_time_range || '1d'}</span>
                      <span>•</span>
                      <span>{post.news_auto_select ? 'AI Select' : 'Latest'}</span>
                    </>
                  )}
                </div>
                <div className="queue-item-actions">
                  {post.status === 'pending' && (
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => onDeleteScheduled(post.id)}
                    >
                      Cancel
                    </button>
                  )}
                  {post.status === 'failed' && post.error_message && (
                    <span className="error-hint" title={post.error_message}>⚠️</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}

export default App
