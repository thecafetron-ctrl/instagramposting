import { useState, useEffect } from 'react'
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
    // Get public base URL - for local dev, user needs ngrok or similar
    const savedUrl = localStorage.getItem('instagram_public_url') || ''
    const publicUrl = prompt(
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
      const data = await res.json()
      if (data.status === 'success') {
        alert(`✅ Posted to Instagram!\n\nPost ID: ${data.instagram_post_id}`)
      } else {
        alert(`❌ Instagram Error:\n\n${data.message}`)
      }
      return data
    } catch (err) {
      console.error('Failed to post to Instagram:', err)
      alert('Failed to post to Instagram: ' + err.message)
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
  const fetchNewsArticles = async () => {
    try {
      const res = await fetch(`${API_BASE}/news/latest?count=10`)
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
      }
      
      // Use custom headline or selected news article
      if (customHeadline) {
        body.custom_headline = customHeadline
      } else if (newsArticles.length > 0) {
        body.custom_headline = newsArticles[selectedNewsIndex]?.title
        body.category = newsArticles[selectedNewsIndex]?.category || newsCategory
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
                
                {/* News Category */}
                <div className="selector-group">
                  <label className="form-label">Category</label>
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
                <div className="selector-group">
                  <label className="form-label">Headline</label>
                  <input
                    type="text"
                    className="form-input"
                    placeholder="Enter custom headline or select from latest news below..."
                    value={customHeadline}
                    onChange={(e) => setCustomHeadline(e.target.value)}
                  />
                </div>

                {/* Latest News Articles */}
                <div className="selector-group">
                  <div className="news-header">
                    <label className="form-label">Or Select from Latest News</label>
                    <button className="btn btn-sm" onClick={fetchNewsArticles}>
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
              </div>

              <button
                className="btn btn-primary btn-lg generate-btn"
                onClick={generateNewsPost}
                disabled={loading || (!customHeadline && newsArticles.length === 0)}
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
    default_template_id: null,
    default_color_theme: null,
    default_texture: null,
    default_layout: null,
    default_slide_count: 4,
    instagram_username: '',
  })
  const [newPostSettings, setNewPostSettings] = useState({
    useDefault: true,
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
      setLocalSettings(settings)
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

      {/* Posting Frequency */}
      <div className="autopost-card">
        <h3>Posting Frequency</h3>
        <div className="frequency-selector">
          <label className="form-label">Posts per day</label>
          <div className="frequency-buttons">
            {[1, 2, 3, 4, 5, 6].map((num) => (
              <button
                key={num}
                className={`freq-btn ${localSettings.posts_per_day === num ? 'selected' : ''}`}
                onClick={() => setLocalSettings({ ...localSettings, posts_per_day: num })}
              >
                {num}
              </button>
            ))}
          </div>
          <p className="form-hint">
            Posts will be spread evenly across 24 hours ({(24 / localSettings.posts_per_day).toFixed(1)} hours apart)
          </p>
        </div>
      </div>

      {/* Default Settings */}
      <div className="autopost-card">
        <h3>Default Post Settings</h3>
        <p className="form-hint">Leave as "Random" to randomize each post's style</p>
        
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
              value={localSettings.default_slide_count}
              onChange={(e) => setLocalSettings({ ...localSettings, default_slide_count: parseInt(e.target.value) })}
            >
              {[4, 5, 6, 7, 8, 9, 10].map((n) => (
                <option key={n} value={n}>{n} slides</option>
              ))}
            </select>
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
              <div key={post.id} className={`queue-item status-${post.status}`}>
                <div className="queue-item-time">
                  <span className="queue-time">{formatTime(post.scheduled_time)}</span>
                  <span className={`queue-status ${post.status}`}>{post.status}</span>
                </div>
                <div className="queue-item-details">
                  <span>{post.template_id || 'Random'}</span>
                  <span>•</span>
                  <span>{post.color_theme || 'Random'}</span>
                  <span>•</span>
                  <span>{post.texture || 'Random'}</span>
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
