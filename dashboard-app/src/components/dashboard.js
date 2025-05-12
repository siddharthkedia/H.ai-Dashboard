import {
  Card,
  CardContent,
  Typography,
  Grid,
  Select,
  MenuItem,
  FormControl,
  Box,
  Button,
  CircularProgress,
  AppBar,
  Toolbar,
  IconButton,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  InputLabel,
  TextField,
} from "@mui/material";
import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import SettingsIcon from "@mui/icons-material/Settings";

const Dashboard = () => {
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState();
  const [endDate, setEndDate] = useState();
  const [frequency, setFrequency] = useState("Weekly");
  const [chartData, setChartData] = useState({});
  const [rawData, setRawData] = useState([]);
  const [prevStartDate, setPrevStartDate] = useState(startDate);
  const [prevEndDate, setPrevEndDate] = useState(endDate);
  const [openSettings, setOpenSettings] = useState(false);
  const [hasData, setHasData] = useState(false);

  useEffect(() => {
    if (metrics.length > 0) {
      setHasData(true);
    } else {
      setHasData(false);
    }
  }, [metrics]);

  const fetchMetrics = async () => {
    setLoading(true);
    try {
      const response = await axios.post(
        "http://127.0.0.1:8000/api/metrics",
        {
          startDate: startDate,
          endDate: endDate,
        },
        {
          params: { botName: "HAiBot" },
        }
      );
      console.log("response fetched");
      const fetchedData = response.data;
      
      setRawData(fetchedData);
      
      const aggregatedData = aggregateData(fetchedData, frequency);
      
      setMetrics(aggregatedData);
      setChartData(formatChartData(aggregatedData));
      setPrevStartDate(startDate);
      setPrevEndDate(endDate);
    } catch (error) {
      console.error("Error fetching data:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleApply = () => {
    console.log("Clicked apply");
    if (!startDate || !endDate) {
      alert("Please select both start and end dates.");
      return;
    }
    if (startDate !== prevStartDate || endDate !== prevEndDate) {
      console.log("Fetching metrics");
      fetchMetrics();
    } else {
      console.log("Aggregating metrics at frontend");
      const aggregatedData = aggregateData(rawData, frequency);
      setMetrics(aggregatedData);
      setChartData(formatChartData(aggregatedData));
    }
  };
  
  const aggregateData = (rawData, frequency) => {
    const periodGroups = {};
    
    rawData.forEach((metric) => {
      const metricName = metric.metric;
      const isMaxMetric = metricName.startsWith("Max ");
      
      metric.values.forEach((entry) => {
        const date = new Date(entry.period);
        let key;
        
        if (frequency === "Daily") {
          key = date.toISOString().split("T")[0];
        }else if (frequency === "Weekly") {
          const weekStart = new Date(date);
          weekStart.setDate(date.getDate() - date.getDay() + 1);
          key = weekStart.toISOString().split("T")[0];
        } else if (frequency === "Monthly") {
          key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
        } else if (frequency === "Quarterly") {
          const quarter = Math.floor(date.getMonth() / 3) + 1;
          key = `${date.getFullYear()}-Q${quarter}`;
        } else if (frequency === "Yearly") {
          key = `${date.getFullYear()}`;
        }
        
        if (!periodGroups[key]) {
          periodGroups[key] = { period: key };
        }

        if (!periodGroups[key][metric.metric]) {
          periodGroups[key][metric.metric] = 0;
        }
        
        if (isMaxMetric) {
          if (!periodGroups[key][metricName] || entry.value > periodGroups[key][metricName]) {
            periodGroups[key][metricName] = entry.value;
          }
        } else {
            periodGroups[key][metricName] += entry.value;
        }
      });
    });
    
    Object.keys(periodGroups).forEach(key => {
      const group = periodGroups[key];
      
      group["Click Through Rate (%)"] = 
        group["Total unique sessions"] > 0 ? Math.round((group["User consented sessions"] / group["Total unique sessions"]) * 100 * 100)/100 : 0;
      
      group["Avg messages per chat session"] = 
        group["Active chat sessions"] > 0 ? Math.round((group["Total messages (active chat sessions)"] / group["Active chat sessions"])*100)/100 : 0;
      
      group["Avg session duration (minutes, active chat sessions)"] = 
      group["Active chat sessions"]  > 0 ? Math.round((group["Total engagement (minutes, active chat sessions)"] / group["Active chat sessions"])*100)/100 : 0;
    });
    
    return Object.values(periodGroups);
  };

  const getMetricType = (metricName) => {
    if (metricName.startsWith("Max ")) return "maximum";
    if (metricName === "Click Through Rate (%)") return "percentage";
    if (metricName === "Avg messages per chat session") return "average";
    if (metricName === "Avg session duration (minutes, active chat sessions)") return "average";
    return "sum";
  };

  const calculateMetricTotal = (metrics, metric) => {
    if (!metrics || metrics.length === 0) return 0;
    
    const metricType = getMetricType(metric);
    
    switch (metricType) {
      case "maximum":
        return Math.max(...metrics.map(entry => entry[metric] || 0));
        
      case "percentage":
        const totalConsented = metrics.reduce((sum, entry) => sum + (entry["User consented sessions"] || 0), 0);
        const totalSessions = metrics.reduce((sum, entry) => sum + (entry["Total unique sessions"] || 0), 0);
        return totalSessions > 0 ? Math.round((totalConsented / totalSessions) * 100 * 100) / 100 : 0;
        
      case "average":
        if (metric === "Avg messages per chat session") {
          const totalMessages = metrics.reduce((sum, entry) => sum + (entry["Total messages (active chat sessions)"] || 0), 0);
          const totalChatSessions = metrics.reduce((sum, entry) => sum + (entry["Active chat sessions"] || 0), 0);
          return totalChatSessions > 0 ? Math.round((totalMessages / totalChatSessions) * 100) / 100 : 0;
        } else if (metric === "Avg session duration (minutes, active chat sessions)") {
          const totalEngagement = metrics.reduce((sum, entry) => sum + (entry["Total engagement (minutes, active chat sessions)"] || 0), 0);
          const totalChatSessions = metrics.reduce((sum, entry) => sum + (entry["Active chat sessions"] || 0), 0);
          return totalChatSessions > 0 ? Math.round((totalEngagement / totalChatSessions) * 100) / 100 : 0;
        }
        return 0;
        
      case "sum":
      default:
        return metrics.reduce((sum, entry) => sum + (entry[metric] || 0), 0);
    }
  };

  const formatChartData = (aggregatedData) => {
    const formattedData = {};
    if (aggregatedData.length === 0) return formattedData;

    Object.keys(aggregatedData[0]).forEach((metric) => {
      if (metric !== "period") {
        formattedData[metric] = aggregatedData.map((entry) => ({
          period: entry.period,
          value: entry[metric] || 0,
        }));
      }
    });

    return formattedData;
  };

  return (
    <Box sx={{ flexGrow: 1 }}>
      <AppBar position="static" sx={{ backgroundColor: "#47ee3f" }}>
        <Toolbar sx={{ display: 'flex', alignItems: 'center', margin: 1 }}>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            Dashboard Metrics
          </Typography>
          <FormControl sx={{ m: 1, minWidth: 120, margin: 1 }} size="small">
            <TextField
              id="start-date"
              type="date"
              label="Start Date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </FormControl>
          <FormControl sx={{ m: 1, minWidth: 120, margin: 1 }} size="small">
            <TextField
              id="end-date"
              type="date"
              label="End Date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />
          </FormControl>
          <FormControl sx={{ m: 1, minWidth: 120, margin: 1 }} size="small">
            <InputLabel id="frequency-label">Frequency</InputLabel>
            <Select
              labelId="frequency-label"
              id="frequency"
              value={frequency}
              label="Frequency"
              onChange={(e) => setFrequency(e.target.value)}
            >
              <MenuItem value="Daily">Daily</MenuItem>
              <MenuItem value="Weekly">Weekly</MenuItem>
              <MenuItem value="Monthly">Monthly</MenuItem>
              <MenuItem value="Quarterly">Quarterly</MenuItem>
              <MenuItem value="Yearly">Yearly</MenuItem>
            </Select>
          </FormControl>
          <Button variant="contained" color="primary" sx={{ ml: 2 }} onClick={handleApply}>
            Apply
          </Button>
        </Toolbar>
      </AppBar>

      <Box padding={3} bgcolor="#f4f4f4" sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 'calc(100vh - 64px)' }}>
        {!hasData && !loading ? (
          <Typography variant="h6" color="textSecondary">
            Please select a start and end date and click "Apply" to load data.
          </Typography>
        ) : loading ? (
            <CircularProgress />
        ) : (
          <>
            <Grid container spacing={2} marginTop={2}>
              {Object.keys(chartData).map((metric, index) => (
              <Grid item xs={12} sm={6} md={4} lg={4} key={index} sx={{ minWidth: "30% " }}>
                <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <CardContent sx={{ flexGrow: 1 }}>
                      <Typography variant="h6" gutterBottom fontWeight="bold">
                        {metric}
                      </Typography>
                    <Typography variant="body2" color="text.secondary">
                        Total: {calculateMetricTotal(metrics, metric)}
                    </Typography>
                    <ResponsiveContainer width="100%" height="80%">
                        <LineChart data={chartData[metric]}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="period" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="#8884d8"
                            strokeWidth={2}
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </>
        )}
      </Box>
    </Box>
  );
};

export default Dashboard;
