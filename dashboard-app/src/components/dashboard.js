import { Card, CardContent, Typography, Grid, Select, MenuItem, FormControl, InputLabel, Box, Button, CircularProgress } from "@mui/material";
import React, { useState } from "react";
import axios from "axios";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

const MetricCard = ({ title, value }) => (
  <Card sx={{ minWidth: 275, margin: 2, boxShadow: 3, borderRadius: 2 }}>
    <CardContent>
      <Typography variant="h6" component="div" gutterBottom>
        {title}
      </Typography>
      <Typography variant="h5" fontWeight="bold">{value}</Typography>
    </CardContent>
  </Card>
);

const Dashboard = () => {
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(false);
  const [startDate, setStartDate] = useState("2024-11-01");
  const [endDate, setEndDate] = useState("2025-01-31");
  const [frequency, setFrequency] = useState("Weekly");
  const [chartData, setChartData] = useState({});

      const fetchMetrics = async () => {
    setLoading(true);
        try {
        const response = await axios.post("http://127.0.0.1:8000/api/metrics", {
          start_date: startDate,
          end_date: endDate,
        }, {
          params: { bot_name: "HAiBot" }
        });
        const rawData = response.data;
        // console.log('Raw Data->', JSON.stringify(rawData));
        const aggregatedData = aggregateData(rawData, frequency);
        console.log('Aggregate Data->', JSON.stringify(aggregatedData));
        setMetrics(aggregatedData);
      setChartData(formatChartData(aggregatedData));
        } catch (error) {
          console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
        }
      };
  
  // Aggregate Data
      const aggregateData = (rawData, frequency) => {
  const groupedData = {};

  rawData.forEach(metric => {
    metric.values.forEach(entry => {
      const date = new Date(entry.period);
      let key;

      if (frequency === "Weekly") {
        const weekStart = new Date(date);
        weekStart.setDate(date.getDate() - date.getDay() + 1); // Ensure week starts on Monday
        key = weekStart.toISOString().split("T")[0];
      } else if (frequency === "Monthly") {
        key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
      } else if (frequency === "Quarterly") {
        const quarter = Math.floor(date.getMonth() / 3) + 1;
        key = `${date.getFullYear()}-Q${quarter}`;
      } else if (frequency === "Yearly") {
        key = `${date.getFullYear()}`;
      }

      if (!groupedData[key]) {
        groupedData[key] = { period: key };
      }

      if (!groupedData[key][metric.metric]) {
        groupedData[key][metric.metric] = 0;
      }

      groupedData[key][metric.metric] += entry.value;
    });
  });

  return Object.values(groupedData);
};

  // Format Data for Charts (Separate Data for Each Metric)
const formatChartData = (aggregatedData) => {
    const formattedData = {};
    if (aggregatedData.length === 0) return formattedData;

    Object.keys(aggregatedData[0]).forEach(metric => {
      if (metric !== "period") {
        formattedData[metric] = aggregatedData.map(entry => ({
    period: entry.period,
          value: entry[metric] || 0
  }));
      }
    });

    return formattedData;
};

  return (
    <Box display="flex" height="100vh">
      <Box sx={{ width: "25%", padding: 3, bgcolor: "#fff", display: "flex", flexDirection: "column", gap: 2, boxShadow: 2 }}>
        <Typography variant="h6" gutterBottom fontWeight="bold">Filters</Typography>
        <FormControl fullWidth>
          <InputLabel shrink htmlFor="start-date">Start Date</InputLabel>
          <input id="start-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={{ padding: "10px", borderRadius: "4px", border: "1px solid #ccc", width: "100%", marginTop: "5px" }} />
          </FormControl>
        <FormControl fullWidth>
          <InputLabel shrink htmlFor="end-date">End Date</InputLabel>
          <input id="end-date" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={{ padding: "10px", borderRadius: "4px", border: "1px solid #ccc", width: "100%", marginTop: "5px" }} />
          </FormControl>
        <FormControl fullWidth>
          <InputLabel shrink>Frequency</InputLabel>
          <Select value={frequency} onChange={(e) => setFrequency(e.target.value)} style={{ marginTop: "5px" }}>
              <MenuItem value="Weekly">Weekly</MenuItem>
              <MenuItem value="Monthly">Monthly</MenuItem>
              <MenuItem value="Quarterly">Quarterly</MenuItem>
              <MenuItem value="Yearly">Yearly</MenuItem>
            </Select>
          </FormControl>
        <Button variant="contained" color="primary" sx={{ bgcolor: "#000", color: "#fff", ':hover': { bgcolor: "#333" } }} onClick={fetchMetrics}>Apply</Button>
      </Box>
      
      <Box flexGrow={1} padding={3} bgcolor="#f4f4f4">
        <Typography variant="h3" gutterBottom fontWeight="bold">Dashboard Metrics</Typography>
        {loading ? (
          <Box display="flex" justifyContent="center" alignItems="center" height="50vh">
            <CircularProgress />
          </Box>
        ) : (
          <>
      <Grid container spacing={2}>
              {metrics.length > 0 && Object.keys(metrics[0]).map((key, index) => (
                key !== "period" && (
          <Grid item xs={12} sm={6} md={4} key={index}>
                    <MetricCard title={key} value={metrics.reduce((sum, entry) => sum + entry[key], 0)} />
          </Grid>
                )
        ))}
      </Grid>

            {/* Separate Graphs for Each Metric */}
            {Object.keys(chartData).map((metric, index) => (
              <Box key={index} my={4}>
                <Typography variant="h5" gutterBottom fontWeight="bold">{metric}</Typography>
        <ResponsiveContainer width="100%" height={400}>
                  <LineChart data={chartData[metric]}>
            <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="period" />
            <YAxis />
            <Tooltip />
            <Legend />
                    <Line type="monotone" dataKey="value" stroke="#8884d8" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
              </Box>
            ))}
          </>
        )}
      </Box>
    </Box>
  );
};

export default Dashboard;
