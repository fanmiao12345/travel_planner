import { useState, useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Polyline, Popup } from 'react-leaflet'
import { Map as MapIcon, ChevronDown, ChevronUp } from 'lucide-react'
import { fetchRouteData } from '../api/client'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// 修复 Leaflet 默认 marker 图标
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

// 自定义图标
const originIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
})

const destinationIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
})

const waypointIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
})

interface Location {
  name: string
  lat: number
  lng: number
  type: 'origin' | 'destination' | 'waypoint'
}

interface RouteSegment {
  from: string
  to: string
  from_lat: number
  from_lng: number
  to_lat: number
  to_lng: number
}

interface RouteData {
  locations: Location[]
  routes: RouteSegment[]
}

interface Props {
  sessionId: string
}

export default function RouteMap({ sessionId }: Props) {
  const [data, setData] = useState<RouteData | null>(null)
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const load = async () => {
      try {
        const result = await fetchRouteData(sessionId)
        if (result.error) {
          setError(result.error)
        } else if (result.locations?.length > 0) {
          setData(result)
        } else {
          setError('未能提取到路线坐标数据')
        }
      } catch (e: any) {
        setError(e.message || '加载路线数据失败')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [sessionId])

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 bg-gray-800/50 border border-gray-700 rounded-xl text-gray-400 text-sm">
        <MapIcon size={16} className="animate-pulse" />
        正在加载路线地图...
      </div>
    )
  }

  if (error || !data) return null

  const { locations, routes } = data
  if (locations.length === 0) return null

  // 计算地图中心
  const avgLat = locations.reduce((s, l) => s + l.lat, 0) / locations.length
  const avgLng = locations.reduce((s, l) => s + l.lng, 0) / locations.length

  // 计算缩放级别
  const latRange = Math.max(...locations.map(l => l.lat)) - Math.min(...locations.map(l => l.lat))
  const lngRange = Math.max(...locations.map(l => l.lng)) - Math.min(...locations.map(l => l.lng))
  const maxRange = Math.max(latRange, lngRange)
  const zoom = maxRange < 0.5 ? 12 : maxRange < 2 ? 9 : maxRange < 5 ? 7 : 5

  const getIcon = (type: string) => {
    if (type === 'origin') return originIcon
    if (type === 'destination') return destinationIcon
    return waypointIcon
  }

  const typeLabel = (type: string) => {
    if (type === 'origin') return '🟢 出发地'
    if (type === 'destination') return '🔴 目的地'
    return '🔵 途经点'
  }

  return (
    <div className="border border-gray-700 rounded-xl overflow-hidden">
      {/* 标题栏 */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between p-3 bg-gray-800/80 hover:bg-gray-800 text-sm"
      >
        <span className="flex items-center gap-2 text-travel-400">
          <MapIcon size={16} />
          路线地图 ({locations.length} 个地点)
        </span>
        {collapsed ? <ChevronDown size={16} className="text-gray-500" /> : <ChevronUp size={16} className="text-gray-500" />}
      </button>

      {/* 地图 */}
      {!collapsed && (
        <div className="h-80 relative">
          <MapContainer
            center={[avgLat, avgLng]}
            zoom={zoom}
            style={{ height: '100%', width: '100%' }}
            scrollWheelZoom={true}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {/* 地点标记 */}
            {locations.map((loc, i) => (
              <Marker key={i} position={[loc.lat, loc.lng]} icon={getIcon(loc.type)}>
                <Popup>
                  <div className="text-sm">
                    <strong>{loc.name}</strong>
                    <br />
                    <span className="text-gray-500">{typeLabel(loc.type)}</span>
                    <br />
                    <span className="text-xs text-gray-400">{loc.lat.toFixed(4)}, {loc.lng.toFixed(4)}</span>
                  </div>
                </Popup>
              </Marker>
            ))}
            {/* 路线连线 */}
            {routes.map((r, i) => (
              <Polyline
                key={i}
                positions={[[r.from_lat, r.from_lng], [r.to_lat, r.to_lng]]}
                color="#14b8a6"
                weight={3}
                dashArray="8 4"
              />
            ))}
          </MapContainer>
        </div>
      )}

      {/* 地点列表 */}
      {!collapsed && (
        <div className="p-3 bg-gray-800/50 border-t border-gray-700">
          <div className="flex flex-wrap gap-2">
            {locations.map((loc, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-1 bg-gray-700 rounded-full text-xs text-gray-300">
                <span>{typeLabel(loc.type).split(' ')[0]}</span>
                {loc.name}
                {i < locations.length - 1 && <span className="text-gray-500 ml-1">→</span>}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
