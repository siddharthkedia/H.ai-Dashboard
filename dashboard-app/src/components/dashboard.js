import { Card, CardContent, Typography, Grid, Select, MenuItem, FormControl, InputLabel, Drawer, Box } from "@mui/material";
import React, { useState, useEffect } from "react";
import axios from "axios";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

const MetricCard = ({ title, value }) => (
  <Card sx={{ minWidth: 275, margin: 2 }}>
    <CardContent>
      <Typography variant="h6" component="div" gutterBottom>
        {title}
      </Typography>
      <Typography variant="h5">{value}</Typography>
    </CardContent>
  </Card>
);

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [metrics, setMetrics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [startDate, setStartDate] = useState("2024-01-01");
  const [endDate, setEndDate] = useState("2024-01-31");
  const [frequency, setFrequency] = useState("Monthly");
  const [chartData, setChartData] = useState([]);
  

  // Fetch metrics data from the backend using Axios
  useEffect(() => {
    // Fetch data from backend
    // axios.get('http://127.0.0.1:8000/api/compare-weekly')
    //   .then(response => {
    //     setData(response.data);
    //     setLoading(false);
    //   })
    //   .catch(error => {
    //     console.error('Error fetching data:', error);
    //     setLoading(false);
    //   });
      // console.log('data-->',data);
      const fetchMetrics = async () => {
        try {
        const response = await axios.post("http://127.0.0.1:8000/api/metrics", {
          start_date: startDate,
          end_date: endDate,
        }, {
          params: { bot_name: "HAiBot", frequency }
        });
        setMetrics(response.data);
        setChartData(response.data.map((item) => ({ date: item.metric, value: item.value })));
        } catch (error) {
          console.error("Error fetching data:", error);
      } finally {
        setLoading(false);
        }
      };
  
      fetchMetrics();
  }, [startDate, endDate, frequency]);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <Box display="flex" height="100vh">
      <Box sx={{ width: 250, padding: 2, bgcolor: "#f4f4f4" }}>
        <Typography variant="h6" gutterBottom>Filters</Typography>
        <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>Start Date</InputLabel>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </FormControl>
        <FormControl fullWidth sx={{ mb: 2 }}>
            <InputLabel>End Date</InputLabel>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </FormControl>
        <FormControl fullWidth>
            <InputLabel>Frequency</InputLabel>
            <Select value={frequency} onChange={(e) => setFrequency(e.target.value)}>
              <MenuItem value="Weekly">Weekly</MenuItem>
              <MenuItem value="Monthly">Monthly</MenuItem>
              <MenuItem value="Quarterly">Quarterly</MenuItem>
              <MenuItem value="Yearly">Yearly</MenuItem>
            </Select>
          </FormControl>
      </Box>
      <Box flexGrow={1} padding={3}>
      <Typography variant="h3" gutterBottom>
        Dashboard Metrics
      </Typography>
      <Grid container spacing={2}>
        {/* <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Total Unique Sessions"
            value={metrics.totalUniqueSessions}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Total User Consented Sessions"
            value={metrics.totalUserConsentedSessions}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="CTR (%)"
            value={`${metrics.ctr}%`}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Total Chat Sessions"
            value={metrics.totalChatSessions}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Total Chat Session Messages"
            value={metrics.totalChatMessages}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Average Messages Per Chat Session"
            value={metrics.avgMessagesPerSession.toFixed(2)}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Max Messages In A Single Chat Session"
            value={metrics.maxMessagesInSession}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Total Engagement Time (min)"
            value={metrics.totalEngagementTime}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Avg Engagement Time Per Chat Session (min)"
            value={metrics.avgEngagementTimePerSession}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Max Engagement Time In A Single Chat Session (min)"
            value={metrics.maxEngagementTimeInSession}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="OTP Logged In Chat Sessions"
            value={metrics.otpLoggedInSessions}
          />
        </Grid>
        <Grid item xs={12} sm={6} md={4}>
          <MetricCard
            title="Manually Logged Out Chat Sessions"
            value={metrics.manuallyLoggedOutSessions}
          />
        </Grid> */}
        {metrics.map((metric, index) => (
          <Grid item xs={12} sm={6} md={4} key={index}>
            <MetricCard title={metric.metric} value={metric.value} />
          </Grid>
        ))}
      </Grid>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" stroke="#8884d8" />
          </LineChart>
        </ResponsiveContainer>
      </Box>
    </Box>
  );
};

export default Dashboard;
