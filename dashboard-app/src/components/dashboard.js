import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Grid } from '@mui/material';

import axios from 'axios';

const MetricCard = ({ title, value }) => (
  <Card sx={{ minWidth: 275, margin: 2 }}>
    <CardContent>
      <Typography variant="h5" component="div" gutterBottom>
        {title}
      </Typography>
      <Typography variant="h6">
        {value}
      </Typography>
      {/* {Icon && <Icon size={50} />} */}
    </CardContent>
  </Card>
);

const Dashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [metrics, setMetrics] = useState(null);

  // Fetch metrics data from the backend using Axios
  useEffect(() => {
    // Fetch data from backend
    axios.get('http://127.0.0.1:8000/api/compare-weekly')
      .then(response => {
        setData(response.data);
        setLoading(false);
      })
      .catch(error => {
        console.error('Error fetching data:', error);
        setLoading(false);
      });
      console.log('data-->',data);
      const fetchMetrics = async () => {
        try {
          const response = await axios.get("http://127.0.0.1:8000/api/metrics");
          setMetrics(response.data);  // Store the data in state
        } catch (error) {
          console.error("Error fetching data:", error);
        }
      };
  
      fetchMetrics();
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }
  if (!metrics) {
    return <div>Loading...</div>;
  }

  return (
    // <div>
    //   <h1>Dashboard</h1>
    //   <ResponsiveContainer width="100%" height={400}>
    //     <LineChart data={data}>
    //       <CartesianGrid strokeDasharray="3 3" />
    //       <XAxis dataKey="period" />
    //       <YAxis />
    //       <Tooltip />
    //       <Legend />
    //       <Line type="monotone" dataKey="value" stroke="#8884d8" />
    //     </LineChart>
    //   </ResponsiveContainer>
    // </div>
    
    <div style={{ padding: '20px' }}>
      <Typography variant="h3" gutterBottom>
        Dashboard Metrics
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} sm={6} md={4}>
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
        </Grid>
      </Grid>
    </div>
  );
};

export default Dashboard;
