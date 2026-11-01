import { Cell, Pie, PieChart, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip } from 'recharts'

const PIE_COLORS = ['#41d9ff', '#334155', '#fbbf24']

export default function ExposureCharts({ found, missing, unverified, categories }) {
  const pieData = [
    { name: 'Found', value: found },
    { name: 'Not found', value: missing },
    { name: 'Unverified', value: unverified },
  ]
  const radarData = [
    { subject: 'Social', value: categories.social ? 100 : 0 },
    { subject: 'Professional', value: categories.professional ? 100 : 0 },
    { subject: 'Developer', value: categories.developer ? 100 : 0 },
    { subject: 'Messaging', value: categories.messaging ? 100 : 0 },
    { subject: 'Content', value: categories.content ? 100 : 0 },
  ]

  return (
    <section className="chart-grid">
      <div className="glass-card chart-card">
        <p className="section-kicker">07 / exposure distribution</p>
        <h2 className="section-title mt-2">Platform coverage</h2>
        <div className="chart-wrap chart-wrap-pie">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={pieData} dataKey="value" nameKey="name" innerRadius="62%" outerRadius="82%" paddingAngle={4} animationDuration={900}>
                {pieData.map((entry, index) => <Cell key={entry.name} fill={PIE_COLORS[index]} />)}
              </Pie>
              <Tooltip contentStyle={{ background: '#0b1321', border: '1px solid rgba(65,217,255,.25)', borderRadius: 10 }} />
            </PieChart>
          </ResponsiveContainer>
          <div className="chart-center-label"><strong>{found}</strong><span>of 10 found</span></div>
        </div>
        <div className="chart-legend"><span><i className="legend-found" /> Found</span><span><i className="legend-missing" /> Missing</span></div>
      </div>
      <div className="glass-card chart-card">
        <p className="section-kicker">08 / category intelligence</p>
        <h2 className="section-title mt-2">Exposure radar</h2>
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} outerRadius="72%">
              <PolarGrid stroke="rgba(148,163,184,.18)" />
              <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 10 }} />
              <Radar dataKey="value" stroke="#a78bfa" fill="#8b5cf6" fillOpacity={0.28} animationDuration={900} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  )
}
